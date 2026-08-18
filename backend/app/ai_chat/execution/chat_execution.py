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

import time
import uuid
from typing import Callable

from app.ai_chat.errors import ConversationNotFoundError, InvalidConversationStateError
from app.ai_chat.execution.reasoning_classifier import needs_reasoning
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
from app.api.v1.ally.memory.schemas import MemoryType
from app.core.logger import logger

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
        suggestion_service=None,  # optional -- None means no suggestions generated
        call_logger=None,         # optional -- None means no llm_call_log row written
        memory=None,              # optional M6 MemoryService -- None means no memory write
        clock: Clock | None = None,
        id_factory: Callable[[], str] | None = None,
    ):
        self.context_builder = context_builder
        self.conversation_service = conversation_service
        self.context_window_builder = context_window_builder
        self.prompt_manager = prompt_manager
        self.execution = execution
        self.suggestion_service = suggestion_service
        self.call_logger = call_logger
        self.memory = memory
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

        # Idempotency: a request_id whose full turn (user message + Ally's
        # reply) is already on file means a PRIOR attempt with this exact id
        # already ran to completion -- most often the client gave up on a
        # slow-but-successful call (timeout) and the founder was told to
        # resend. Re-running from here would duplicate the turn in their
        # history and bill the LLM call twice; hand back what already
        # happened instead. A request_id with only a user message (no reply
        # yet) is not treated as complete -- that prior attempt may still be
        # in flight or may have failed before persisting a reply, and this
        # one should be allowed to try again rather than replay nothing.
        if request.request_id:
            prior_user, prior_assistant = self.conversation_service.find_turn_by_request_id(
                conversation.conversation_id, request.request_id,
            )
            if prior_user is not None and prior_assistant is not None:
                logger.info(
                    "chat send_message idempotent replay (request_id already completed)",
                    extra={"conversation_id": conversation.conversation_id, "request_id": request_id},
                )
                return self._replay(request_id, conversation, started, prior_assistant)

        # 3. Append the user message (raises InvalidMessageError on empty content).
        user_message = self.conversation_service.append_message(
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
                                  failed_step=RENDER_PROMPT, error=f"prompt: {exc}",
                                  user_message_id=user_message.message_id)

        # 6. Execute AI (M5 is itself fail-closed -> always returns). Turns that
        # actually need to reason over grounded data (diagnosis/RAG) route to
        # the reasoning-tier model instead of the fast default -- see
        # reasoning_classifier.needs_reasoning and AIRouter.route.
        reasoning_required = needs_reasoning(request.message, ally_context, window)
        ai_started = time.perf_counter()
        ai = self.execution.execute(AIRequest(prompt=rendered, reasoning_required=reasoning_required))
        ai_latency_ms = int(round((time.perf_counter() - ai_started) * 1000))
        completed.append(EXECUTE_AI)

        # Telemetry: llm_call_log has always recorded reasoning-pipeline calls but
        # never chat-path calls (confirmed live -- a real successful chat turn left
        # zero new rows). Best-effort, same fail-open convention as memory/
        # retrieval/graph above: a logging failure must never surface as a chat
        # error, so this is swallowed by call_logger itself, not just by this try.
        if self.call_logger is not None:
            try:
                self.call_logger(
                    ai, founder_id=request.founder_id, session_id=request.session_id,
                    latency_ms=ai_latency_ms,
                )
            except Exception as exc:  # noqa: BLE001 -- telemetry must never break the turn
                logger.warning(
                    "chat call_logger raised; ignoring", exc_info=exc,
                    extra={"conversation_id": conversation.conversation_id},
                )

        # Persist a WORKING memory of the founder's message (M6). Live-confirmed
        # gap: ChatExecutionService never called memory.store() anywhere -- not a
        # write that was failing, a write that was never attempted. This mirrors
        # the (tested, already-reviewed, just never-wired-to-a-live-endpoint)
        # M7 orchestrator's own persist step exactly: same call shape, same
        # WORKING type, same importance=50 default -- not a new policy, the
        # existing one finally reaching the path founders actually use.
        # Unconditional on ai.ok, matching the orchestrator: the founder said
        # this regardless of whether Ally managed to answer it.
        if self.memory is not None:
            try:
                self.memory.store(
                    request.founder_id, MemoryType.WORKING, request.message,
                    importance=50, session_id=request.session_id,
                    correlation_id=request_id, actor="founder",
                )
            except Exception as exc:  # noqa: BLE001 -- fail open, same as memory/retrieval/graph
                logger.warning(
                    "chat memory persist failed; continuing", exc_info=exc,
                    extra={"conversation_id": conversation.conversation_id},
                )

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
        response = self._finalize(request_id, conversation, started, completed, window,
                                  ai=ai, rendered=rendered, assistant_id=assistant_id,
                                  failed_step=failed_step, error=error,
                                  user_message_id=user_message.message_id)

        # 8. Generate suggestions for this conversation now, while THIS turn's
        # context_window/ai_response are actually in hand -- the only place
        # they ever are. GET /conversations/{id}/suggestions just lists what's
        # already here (SuggestionService.list_suggestions) instead of blindly
        # regenerating without that data, which is what left the AI-response-
        # aware rules (rule_follow_up, rule_clarification) permanently unable
        # to fire. Best-effort: never breaks the chat turn on failure. Gated
        # on persist_assistant so streaming's own pre-completion call (which
        # passes False) doesn't generate suggestions for a reply that might
        # still be cancelled -- streaming does not yet get inline suggestions
        # at all as a result; a known, smaller gap than the one this fixes.
        if self.suggestion_service is not None and persist_assistant:
            try:
                self.suggestion_service.generate_suggestions(
                    conversation, context_window=window, ai_response=response,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "suggestion generation failed after a chat turn; conversation unaffected",
                    extra={"conversation_id": conversation.conversation_id},
                    exc_info=exc,
                )

        return response

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

    # --- idempotent replay -------------------------------------------------

    def _replay(self, request_id, conversation, started, assistant_message) -> ChatResponse:
        """Reconstruct the ChatResponse for a turn that already completed under
        this request_id, without re-running the pipeline.

        Not a full-fidelity replay: response_type comes back from the
        assistant message's stored metadata, but confidence and citations are
        never persisted on the message row (only the reasoning pipeline's own
        report carries those) and come back empty/None here. That is a real,
        narrower response than the original call got -- accepted because this
        path only fires for a retried request_id, never a normal turn, and the
        alternative (re-running the LLM call) is worse: double billing and a
        duplicated turn in the founder's history.
        """
        finished = self.clock.now()
        duration_ms = round((finished - started).total_seconds() * 1000, 3)
        meta = assistant_message.metadata or {}
        usage = assistant_message.token_usage
        token_usage = TokenUsage.of(usage.prompt_tokens, usage.completion_tokens) if usage else TokenUsage()

        metrics = ChatMetrics(token_usage=token_usage)
        trace = ConversationExecutionTrace(
            request_id=request_id, conversation_id=conversation.conversation_id,
            started_at=started, finished_at=finished, duration_ms=duration_ms,
            completed_steps=(LOAD_CONVERSATION, "idempotent_replay"), failed_step=None,
            provider=meta.get("provider"), model=meta.get("model"),
            memory_injected=False, retrieval_injected=False, graph_injected=False,
            metrics=metrics,
        )
        return ChatResponse(
            request_id=request_id, conversation_id=conversation.conversation_id, ok=True,
            answer=assistant_message.content,
            response_type=meta.get("response_type") or "answer",
            confidence=None, citations=(),
            assistant_message_id=assistant_message.message_id,
            # Replay does not re-append the user turn (that is the point), so
            # there is no new message to hand attachments to. The original
            # send already linked them.
            user_message_id=None,
            trace=trace, metrics=metrics, error=None,
        )

    # --- finalize --------------------------------------------------------

    def _finalize(self, request_id, conversation, started, completed, window,
                  *, ai, rendered, assistant_id, failed_step, error,
                  user_message_id=None) -> ChatResponse:
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
            assistant_message_id=assistant_id, user_message_id=user_message_id,
            trace=trace, metrics=metrics, error=error,
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
