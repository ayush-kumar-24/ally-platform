"""Chat API router (Phase 6, Milestone 6).

Transport only: every endpoint maps a request to an existing service call and maps
the result to a response model. No business logic lives here -- routers call
services. Domain errors propagate to the global AppError handler for consistent JSON.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import StreamingResponse

from app.ai_chat.schemas.chat import ChatRequest
from app.ai_chat.streaming.schemas import StreamingChatRequest
from app.ai_chat.suggestions.schemas import SuggestionFeedbackType
from app.api.v1.chat.dependencies import (
    get_attachment_service,
    get_chat_service,
    get_conversation_service,
    get_current_founder_id,
    get_streaming_service,
    get_suggestion_service,
)
from app.api.v1.chat.errors import owned_attachment, owned_conversation, owned_suggestion
from app.api.v1.chat.events import sse_event_stream
from app.api.v1.chat.responses import (
    ApiChatResponse,
    AttachmentListResponse,
    AttachmentResponse,
    ConversationListResponse,
    ConversationMessagesResponse,
    ConversationResponse,
    FeedbackResponse,
    MessageResponse,
    SuggestionCollectionResponse,
    SuggestionResponse,
)
from app.api.v1.chat.schemas import (
    CreateConversationRequest,
    FeedbackRequest,
    MessageRequest,
    StreamRequest,
)

from app.api.v1.plans.dependencies import ChatGate, chat_gate
from app.middleware.rate_limit import founder_rate_limit

router = APIRouter(prefix="/chat", tags=["chat"])

# Named module-level dependency objects, not inline `Depends(founder_rate_limit(...))`
# calls -- FastAPI's `dependency_overrides` keys by the exact callable object
# passed to Depends(), and a factory call produces a fresh closure every time.
# Naming these lets tests override them the same way chat_gate already is
# (see test_api_chat_e2e.py's `world` fixture): this suite validates the chat
# pipeline's own throughput/concurrency, not this rate limiter, which has its
# own dedicated tests (test_rate_limit.py).
message_rate_limit = founder_rate_limit(
    key="chat-message", limit=20, window_seconds=60,
    founder_id_dependency=get_current_founder_id,
)
stream_rate_limit = founder_rate_limit(
    key="chat-stream", limit=20, window_seconds=60,
    founder_id_dependency=get_current_founder_id,
)


# --- messaging --------------------------------------------------------------


@router.post(
    "/message",
    response_model=ApiChatResponse,
    summary="Send a chat message",
    # chat_gate (below) enforces plan/credit limits, but only when
    # PLAN_ENFORCEMENT_ENABLED is on -- with it off (the documented default),
    # chat_gate is a full pass-through and this is the only ceiling on how
    # fast one account can drive LLM spend.
    dependencies=[Depends(message_rate_limit)],
)
def post_message(
    payload: MessageRequest,
    gate: ChatGate = Depends(chat_gate),
    service=Depends(get_chat_service),
) -> ApiChatResponse:
    # `chat_gate` has already enforced plan / daily-token / credit limits before we
    # get here, so the frozen ChatExecutionService below is untouched.
    result = service.send_message(ChatRequest(
        founder_id=gate.founder_id, message=payload.message,
        conversation_id=payload.conversation_id,
        session_id=payload.session_id, language=payload.language,
        response_category=payload.response_category, request_id=payload.request_id,
    ))

    # Charge for real usage, not an estimate -- the true token count only exists
    # once the model has replied.
    usage = getattr(getattr(result, "metrics", None), "token_usage", None)
    tokens = (getattr(usage, "prompt_tokens", 0) or 0) + (getattr(usage, "completion_tokens", 0) or 0)
    if tokens:
        gate.record(tokens)

    return ApiChatResponse.from_domain(result)


@router.post(
    "/stream",
    summary="Stream a chat response (Server-Sent Events)",
    dependencies=[Depends(stream_rate_limit)],
)
def post_stream(
    payload: StreamRequest,
    gate: ChatGate = Depends(chat_gate),
    service=Depends(get_streaming_service),
) -> StreamingResponse:
    # Same gate as /message. Without it, streaming would be a complete bypass of
    # plan limits -- and it is the path the app is moving to, so an ungated
    # /stream would mean the limits stop applying to almost everybody.
    request = StreamingChatRequest(
        founder_id=gate.founder_id, message=payload.message,
        conversation_id=payload.conversation_id,
        session_id=payload.session_id, language=payload.language,
        response_category=payload.response_category, request_id=payload.request_id,
        max_chunk_size=payload.max_chunk_size, timeout_seconds=payload.timeout_seconds,
    )
    # The generator appends its StreamingResponse here once the stream ends;
    # sse_event_stream turns that into the closing `summary` event, which is how
    # a streaming client learns the conversation_id and assistant_message_id.
    summary_sink: list = []
    return StreamingResponse(
        sse_event_stream(
            metered_stream(service.stream(request, sink=summary_sink), gate),
            summary_sink=summary_sink,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def metered_stream(events, gate: ChatGate):
    """Pass events through, then charge once the stream finishes.

    Charging can only happen at the end -- the token count is not known until the
    last chunk. The charge is in a `finally` so a client that disconnects mid-stream
    is still billed for what the provider actually generated; otherwise hanging up
    early would be a free-usage loophole.
    """
    tokens = 0
    try:
        for event in events:
            usage = getattr(getattr(event, "metrics", None), "token_usage", None)
            if usage is not None:
                tokens = ((getattr(usage, "prompt_tokens", 0) or 0)
                          + (getattr(usage, "completion_tokens", 0) or 0)) or tokens
            yield event
    finally:
        if tokens:
            gate.record(tokens, source="stream", reason="Ally chat (streamed)")


# --- conversations ----------------------------------------------------------


@router.get("/conversations", response_model=ConversationListResponse, summary="List conversations")
def list_conversations(
    include_archived: bool = False,
    founder_id: int = Depends(get_current_founder_id),
    service=Depends(get_conversation_service),
) -> ConversationListResponse:
    items = service.list_conversations(founder_id, include_archived=include_archived)
    return ConversationListResponse(
        conversations=[ConversationResponse.from_domain(c) for c in items], total=len(items))


@router.post("/conversations", response_model=ConversationResponse,
             status_code=status.HTTP_201_CREATED, summary="Create a conversation")
def create_conversation(
    payload: CreateConversationRequest,
    founder_id: int = Depends(get_current_founder_id),
    service=Depends(get_conversation_service),
) -> ConversationResponse:
    conversation = service.create_conversation(founder_id, title=payload.title)
    return ConversationResponse.from_domain(conversation)


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse,
            summary="Conversation details")
def get_conversation(
    conversation_id: str,
    founder_id: int = Depends(get_current_founder_id),
    service=Depends(get_conversation_service),
) -> ConversationResponse:
    return ConversationResponse.from_domain(owned_conversation(service, conversation_id, founder_id))


@router.get("/conversations/{conversation_id}/messages", response_model=ConversationMessagesResponse,
            summary="Conversation transcript")
def get_conversation_messages(
    conversation_id: str,
    founder_id: int = Depends(get_current_founder_id),
    service=Depends(get_conversation_service),
) -> ConversationMessagesResponse:
    """The actual transcript -- GET /conversations/{id} above returns only the
    header (title, counts, timestamps). Opening a past conversation needs both;
    the frontend previously had nowhere to get this from at all, so every
    reopened conversation rendered empty regardless of how many messages it
    really had. ConversationService.get_history already existed and was never
    wired to a route."""
    owned_conversation(service, conversation_id, founder_id)
    messages = service.get_history(conversation_id)
    return ConversationMessagesResponse(
        conversation_id=conversation_id,
        messages=[MessageResponse.from_domain(m) for m in messages],
    )


@router.delete("/conversations/{conversation_id}", response_model=ConversationResponse,
               summary="Archive a conversation")
def archive_conversation(
    conversation_id: str,
    founder_id: int = Depends(get_current_founder_id),
    service=Depends(get_conversation_service),
) -> ConversationResponse:
    owned_conversation(service, conversation_id, founder_id)
    return ConversationResponse.from_domain(service.archive_conversation(conversation_id))


@router.post("/conversations/{conversation_id}/restore", response_model=ConversationResponse,
             summary="Restore a conversation")
def restore_conversation(
    conversation_id: str,
    founder_id: int = Depends(get_current_founder_id),
    service=Depends(get_conversation_service),
) -> ConversationResponse:
    owned_conversation(service, conversation_id, founder_id)
    return ConversationResponse.from_domain(service.restore_conversation(conversation_id))


# --- attachments ------------------------------------------------------------


@router.post("/attachments", response_model=AttachmentResponse,
             status_code=status.HTTP_201_CREATED, summary="Upload attachment metadata")
def upload_attachment(
    conversation_id: str = Form(...),
    file: UploadFile = File(...),
    founder_id: int = Depends(get_current_founder_id),
    conversations=Depends(get_conversation_service),
    service=Depends(get_attachment_service),
) -> AttachmentResponse:
    # Ownership must be checked before the write: without it, any authenticated
    # founder could upload an attachment into another founder's conversation_id
    # (guessed, leaked via logs, or a future share feature) and inject content
    # into that founder's AI context. Every other route in this file already
    # does this check; this one was missed.
    owned_conversation(conversations, conversation_id, founder_id)
    # Bytes are read only to derive metadata (size + checksum). Contents are never
    # parsed, embedded or OCR'd.
    content = file.file.read()
    attachment = service.add_attachment(conversation_id, founder_id, file.filename or "", content)
    return AttachmentResponse.from_domain(attachment)


@router.get("/attachments/{attachment_id}", response_model=AttachmentResponse,
            summary="Attachment metadata")
def get_attachment(
    attachment_id: str,
    founder_id: int = Depends(get_current_founder_id),
    service=Depends(get_attachment_service),
) -> AttachmentResponse:
    return AttachmentResponse.from_domain(owned_attachment(service, attachment_id, founder_id))


@router.get("/conversations/{conversation_id}/attachments", response_model=AttachmentListResponse,
            summary="List conversation attachments")
def list_conversation_attachments(
    conversation_id: str,
    include_archived: bool = False,
    founder_id: int = Depends(get_current_founder_id),
    conversations=Depends(get_conversation_service),
    service=Depends(get_attachment_service),
) -> AttachmentListResponse:
    owned_conversation(conversations, conversation_id, founder_id)
    items = service.list_attachments(conversation_id, include_archived=include_archived)
    return AttachmentListResponse(
        attachments=[AttachmentResponse.from_domain(a) for a in items], total=len(items))


@router.delete("/attachments/{attachment_id}", response_model=AttachmentResponse,
               summary="Archive an attachment")
def archive_attachment(
    attachment_id: str,
    founder_id: int = Depends(get_current_founder_id),
    service=Depends(get_attachment_service),
) -> AttachmentResponse:
    owned_attachment(service, attachment_id, founder_id)
    return AttachmentResponse.from_domain(service.archive_attachment(attachment_id))


@router.post("/attachments/{attachment_id}/restore", response_model=AttachmentResponse,
             summary="Restore an attachment")
def restore_attachment(
    attachment_id: str,
    founder_id: int = Depends(get_current_founder_id),
    service=Depends(get_attachment_service),
) -> AttachmentResponse:
    owned_attachment(service, attachment_id, founder_id)
    return AttachmentResponse.from_domain(service.restore_attachment(attachment_id))


# --- suggestions ------------------------------------------------------------


@router.get("/conversations/{conversation_id}/suggestions", response_model=SuggestionCollectionResponse,
            summary="List suggestions already generated for a conversation")
def get_suggestions(
    conversation_id: str,
    founder_id: int = Depends(get_current_founder_id),
    conversations=Depends(get_conversation_service),
    service=Depends(get_suggestion_service),
) -> SuggestionCollectionResponse:
    """Lists what ChatExecutionService already generated right after the last
    chat turn (see send_message step 8) -- it does NOT regenerate here.
    Regenerating on every GET, without that turn's context_window/ai_response
    in hand, is what previously left the AI-response-aware rules
    (rule_follow_up, rule_clarification) permanently unable to fire: this
    endpoint had no way to reconstruct what only the chat turn itself knows.
    """
    owned_conversation(conversations, conversation_id, founder_id)
    suggestions = service.list_suggestions(conversation_id)
    return SuggestionCollectionResponse(
        conversation_id=conversation_id, founder_id=founder_id,
        suggestions=[SuggestionResponse.from_domain(s) for s in suggestions],
        generated=len(suggestions), returned=len(suggestions),
        suppressed=0, limited=False,
    )


@router.post("/suggestions/{suggestion_id}/feedback", response_model=FeedbackResponse,
             summary="Record feedback on a suggestion")
def suggestion_feedback(
    suggestion_id: str,
    payload: FeedbackRequest,
    founder_id: int = Depends(get_current_founder_id),
    service=Depends(get_suggestion_service),
) -> FeedbackResponse:
    owned_suggestion(service, suggestion_id, founder_id)
    feedback = service.record_feedback(
        suggestion_id, SuggestionFeedbackType(payload.feedback), note=payload.note)
    return FeedbackResponse.from_domain(feedback)
