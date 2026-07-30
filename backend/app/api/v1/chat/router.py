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
    get_link_extractor,
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
    ConversationResponse,
    FeedbackResponse,
    SuggestionCollectionResponse,
)
from app.api.v1.chat.schemas import (
    CreateConversationRequest,
    FeedbackRequest,
    MessageRequest,
    StreamRequest,
)

router = APIRouter(prefix="/chat", tags=["chat"])


# --- messaging --------------------------------------------------------------


@router.post("/message", response_model=ApiChatResponse, summary="Send a chat message")
def post_message(
    payload: MessageRequest,
    founder_id: int = Depends(get_current_founder_id),
    service=Depends(get_chat_service),
) -> ApiChatResponse:
    result = service.send_message(ChatRequest(
        founder_id=founder_id, message=payload.message, conversation_id=payload.conversation_id,
        session_id=payload.session_id, language=payload.language,
        response_category=payload.response_category, request_id=payload.request_id,
    ))
    return ApiChatResponse.from_domain(result)


@router.post("/stream", summary="Stream a chat response (Server-Sent Events)")
def post_stream(
    payload: StreamRequest,
    founder_id: int = Depends(get_current_founder_id),
    service=Depends(get_streaming_service),
) -> StreamingResponse:
    request = StreamingChatRequest(
        founder_id=founder_id, message=payload.message, conversation_id=payload.conversation_id,
        session_id=payload.session_id, language=payload.language,
        response_category=payload.response_category, request_id=payload.request_id,
        max_chunk_size=payload.max_chunk_size, timeout_seconds=payload.timeout_seconds,
    )
    return StreamingResponse(
        sse_event_stream(service.stream(request)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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
    service=Depends(get_attachment_service),
) -> AttachmentResponse:
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
            summary="Generate suggestions for a conversation")
def get_suggestions(
    conversation_id: str,
    founder_id: int = Depends(get_current_founder_id),
    conversations=Depends(get_conversation_service),
    attachments=Depends(get_attachment_service),
    links=Depends(get_link_extractor),
    service=Depends(get_suggestion_service),
) -> SuggestionCollectionResponse:
    conversation = owned_conversation(conversations, conversation_id, founder_id)
    conversation_attachments = attachments.list_attachments(conversation_id)
    conversation_links = links.from_messages(conversations.get_history(conversation_id))
    collection = service.generate_suggestions(
        conversation, attachments=conversation_attachments, links=conversation_links)
    return SuggestionCollectionResponse.from_domain(collection)


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
