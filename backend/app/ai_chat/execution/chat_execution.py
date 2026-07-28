"""ChatExecutionService (Phase 6, Milestone 2, Parts 2/3/6).

The chat-flow composition root. It coordinates -- and only coordinates -- existing
systems into one contextual turn:

    build AllyContext (M1)          [frozen]
      -> resolve/create conversation (M1 ConversationService)
      -> append user message         (M1)
      -> ContextWindowBuilder        (composes M6 memory + M3 retrieval + M4 graph)
      -> GroundedPromptManager.render_grounded()   (M2.1, frozen)
      -> AIExecutionService.execute()              (M5, frozen, itself fail-closed)
      -> append assistant message    (M1)          [automatic persistence]
      -> ChatResponse

It holds NO business logic of its own and duplicates none. Deterministic given the
same inputs, subsystems and injected clock/id_factory.

Error policy (Part 6):
  * Precondition errors (unknown founder, missing/foreign/archived/deleted
    conversation, empty message) RAISE a typed error -> the API maps them to 4xx.
  * Degradable sources (memory/retrieval/graph) fail closed inside the builder:
    the turn continues, the trace records what was skipped.
  * Prompt/AI failure (e.g. no diagnosis, timeout) -> a well-formed ChatResponse
    with ok=False and the failing step named; no assistant message is persisted.
"""

from __future__ import annotations

import uuid
from typing import Callable

from app.ai_chat.errors import ConversationNotFoundError, InvalidConversationStateError
from app.ai_chat.schemas.chat import (
    ChatMetrics,
    ChatRequest,
    ChatResponse,
    ConversationContextWindow,
    ConversationExecutionTrace,
)
from app.ai_chat.schemas.conversation import MessageTokenUsage, MessageRole
from app.api.v1.ally.execution.schemas import AIRequest, TokenUsage
from app.api.v1.ally.memory.clock import Clock, SystemClock

BUILD_CONTEXT = "build_context"
LOAD_CONVERSATION = "load_conversation"
APPEND_USER = "append_user_message"
BUILD_WINDOW = "build_context_window"
RENDER_PROMPT = "render_prompt"
EXECUTE_AI = "execute_ai"
APPEND_ASSISTANT = "append_assistant_message"


class ChatExecutionService:
    def __init__(
        self,
        *,
        context_builder,          # M1 AllyContextBuilder (frozen)
        conversation_service,     # M1 ConversationService
        context_window_builder,   # M2 ContextWindowBuilder
        prompt_manager,           # M2.1 GroundedPromptManager (frozen)
        execution,                # M5 AIExecutionService (frozen)
        clock: Clock | None = None,
        id_factory: Callable[[], str] | None = None,
    ):
        self.context_builder = context_builder
        self.conversation_service = conversation_service
        self.context_window_builder = context_window_builder
        self.prompt_manager = prompt_manager
        self.execution = execution
        self.clock = clock or SystemClock()
        self._new_id = id_factory or (lambda: uuid.uuid4().hex)

    def send_message(self, request: ChatRequest, *, persist_assistant: bool = True) -> ChatResponse:
        """Run one contextual chat turn.

        `persist_assistant` (default True) preserves the Milestone-2 behaviour: the
        assistant reply is appended to the conversation before returning. The
        streaming layer passes False so it can persist the assistant ONLY after the
        stream completes (and never on cancel) -- the turn is otherwise identical.
        """
        started = self.clock.now()
        request_id = request.request_id or self._new_id()
        completed: list[str] = []

        # 1. Build AllyContext (M1). Unknown founder raises -> meaningful 4xx.
        ally_context = self.context_builder.build(request.founder_id, request.session_id)
        completed.append(BUILD_CONTEXT)

        # 2. Resolve or create the conversation (raises on missing/foreign/archived).
        conversation = self._resolve_conversation(request)
        completed.append(LOAD_CONVERSATION)

        # 3. Append the user message (raises InvalidMessageError on empty content).
        self.conversation_service.append_message(
            conversation.conversation_id, MessageRole.USER, request.message,
            metadata={"request_id": request_id, "actor": request.actor},
        )
        conversation = self.conversation_service.get_conversation(conversation.conversation_id)
        completed.append(APPEND_USER)

        # 4. Assemble the context window (composes memory + retrieval + graph).
        window = self.context_window_builder.build(
            ally_context=ally_context, conversation=conversation,
            current_message=request.message, language=request.language,
            response_category=request.response_category,
        )
        completed.append(BUILD_WINDOW)

        # 5. Grounded prompt (M2.1). Missing diagnosis vars -> fail closed.
        try:
            rendered = self.prompt_manager.render_grounded(window)
            completed.append(RENDER_PROMPT)
        except Exception as exc:  # noqa: BLE001
            return self._finalize(request_id, conversation, started, completed, window,
                                  ai=None, rendered=None, assistant_id=None,
                                  failed_step=RENDER_PROMPT, error=f"prompt: {exc}")

        # 6. Execute AI (M5 is itself fail-closed -> always returns).
        ai = self.execution.execute(AIRequest(prompt=rendered))
        completed.append(EXECUTE_AI)

        # 7. Persist the assistant reply (automatic) -- only on success, and only
        #    when the caller wants it now (streaming defers this to post-COMPLETE).
        assistant_id = None
        if ai.ok and persist_assistant:
            usage = ai.token_usage or TokenUsage()
            message = self.conversation_service.append_message(
                conversation.conversation_id, MessageRole.ASSISTANT, ai.content,
                token_usage=MessageTokenUsage(usage.prompt_tokens, usage.completion_tokens),
                metadata={
                    "request_id": request_id,
                    "provider": ai.metadata.provider if ai.metadata else None,
                    "model": ai.metadata.model if ai.metadata else None,
                    "response_type": ai.response_type,
                },
            )
            assistant_id = message.message_id
            completed.append(APPEND_ASSISTANT)

        failed_step = None if ai.ok else EXECUTE_AI
        error = None if ai.ok else (ai.error or "ai_execution_failed")
        return self._finalize(request_id, conversation, started, completed, window,
                              ai=ai, rendered=rendered, assistant_id=assistant_id,
                              failed_step=failed_step, error=error)

    # --- conversation resolution -----------------------------------------

    def _resolve_conversation(self, request: ChatRequest):
        if request.conversation_id is None:
            return self.conversation_service.create_conversation(request.founder_id)

        conversation = self.conversation_service.get_conversation(request.conversation_id)
        if conversation.founder_id != request.founder_id:
            # Do not leak existence of another founder's conversation.
            raise ConversationNotFoundError(request.conversation_id)
        if conversation.is_archived:
            raise InvalidConversationStateError(request.conversation_id, "archived", "chat in")
        if conversation.is_deleted:
            raise InvalidConversationStateError(request.conversation_id, "deleted", "chat in")
        return conversation

    # --- finalize --------------------------------------------------------

    def _finalize(self, request_id, conversation, started, completed, window,
                  *, ai, rendered, assistant_id, failed_step, error) -> ChatResponse:
        finished = self.clock.now()
        duration_ms = round((finished - started).total_seconds() * 1000, 3)

        token_usage = ai.token_usage if (ai is not None and ai.ok) else TokenUsage()
        provider = ai.metadata.provider if (ai is not None and ai.metadata is not None) else None
        model = ai.metadata.model if (ai is not None and ai.metadata is not None) else None

        metrics = self._metrics(window, rendered, token_usage)
        trace = ConversationExecutionTrace(
            request_id=request_id, conversation_id=conversation.conversation_id,
            started_at=started, finished_at=finished, duration_ms=duration_ms,
            completed_steps=tuple(completed), failed_step=failed_step,
            provider=provider, model=model,
            memory_injected=window.memory_injected,
            retrieval_injected=window.retrieval_injected,
            graph_injected=window.graph_injected,
            metrics=metrics,
        )
        ok = bool(ai is not None and ai.ok)
        return ChatResponse(
            request_id=request_id, conversation_id=conversation.conversation_id, ok=ok,
            answer=ai.content if ok else "",
            response_type=ai.response_type if ok else "none",
            confidence=ai.confidence if ok else None,
            citations=ai.citations if ok else (),
            assistant_message_id=assistant_id, trace=trace, metrics=metrics, error=error,
        )

    @staticmethod
    def _metrics(window: ConversationContextWindow, rendered, token_usage) -> ChatMetrics:
        return ChatMetrics(
            history_messages=window.history_size,
            included_messages=window.included_size,
            trimmed_messages=window.trimmed_size,
            memory_reads=len(window.memory_items),
            retrieval_hits=len(window.retrieval.items) if window.retrieval is not None else 0,
            graph_nodes=len(window.graph.nodes) if window.graph is not None else 0,
            prompt_version=rendered.version if rendered is not None else None,
            token_usage=token_usage,
        )


def build_chat_execution_service(
    *,
    context_builder,
    memory,
    retrieval,
    knowledge_graph,
    prompt_manager=None,
    execution=None,
    conversation_service=None,
    context_window_builder=None,
    clock: Clock | None = None,
    id_factory: Callable[[], str] | None = None,
) -> ChatExecutionService:
    """Offline-friendly wiring. `context_builder` (M1) must be supplied; the rest
    default to the grounded prompt manager, a mock execution service, an in-memory
    conversation service and a ContextWindowBuilder over the given subsystems."""
    from app.ai_chat.builders.context_window import ContextWindowBuilder
    from app.ai_chat.services.conversation import build_conversation_service
    from app.api.v1.ally.execution.provider import MockLLMProvider
    from app.api.v1.ally.execution.service import build_execution_service
    from app.api.v1.ally.prompts.grounding import default_grounded_prompt_manager

    conversation_service = conversation_service or build_conversation_service(
        clock=clock, id_factory=id_factory
    )
    context_window_builder = context_window_builder or ContextWindowBuilder(
        conversation_service=conversation_service, memory=memory,
        retrieval=retrieval, knowledge_graph=knowledge_graph,
    )
    return ChatExecutionService(
        context_builder=context_builder,
        conversation_service=conversation_service,
        context_window_builder=context_window_builder,
        prompt_manager=prompt_manager or default_grounded_prompt_manager(),
        execution=execution or build_execution_service({"mock": MockLLMProvider()}),
        clock=clock, id_factory=id_factory,
    )
