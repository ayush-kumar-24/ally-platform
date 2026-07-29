"""ContextWindowBuilder (Phase 6, Milestone 2, Part 1).

Assembles the ConversationContextWindow for one chat turn -- purely by COMPOSING
existing systems, with no business-logic duplication:

  * conversation history + deterministic trimming + important-message preservation
    is delegated to the frozen M1 ConversationService.build_context (reused, not
    reimplemented);
  * founder memory (M6), retrieval (M3) and graph expansion (M4) are read through
    their public interfaces and injected fail-closed (a failing source is skipped
    and flagged, never fabricated);
  * recent history is folded into the founder-message text so the grounded prompt
    (which has no dedicated history slot) still sees the conversation -- pure
    composition, no change to the frozen prompt layer.

Deterministic: no token counting, no summarization LLM, stable formatting/ordering.
"""

from __future__ import annotations

from app.ai_chat.schemas.chat import ConversationContextWindow, GroundingRequest
from app.ai_chat.schemas.conversation import Conversation, ConversationContext, MessageRole
from app.api.v1.ally.memory.schemas import MemorySearchRequest
from app.core.logger import logger

_SPEAKER = {MessageRole.USER: "Founder", MessageRole.ASSISTANT: "Ally", MessageRole.SYSTEM: "System"}


class ContextWindowConfig:
    def __init__(self, *, max_history_messages: int = 20, memory_limit: int = 5):
        self.max_history_messages = max_history_messages
        self.memory_limit = memory_limit


class ContextWindowBuilder:
    def __init__(
        self,
        *,
        conversation_service,
        memory,
        retrieval,
        knowledge_graph,
        config: ContextWindowConfig | None = None,
    ):
        self.conversation_service = conversation_service
        self.memory = memory
        self.retrieval = retrieval
        self.knowledge_graph = knowledge_graph
        self.config = config or ContextWindowConfig()

    def build(
        self,
        *,
        ally_context,
        conversation: Conversation,
        current_message: str,
        language: str = "en",
        response_category: str = "diagnosis_answer",
    ) -> ConversationContextWindow:
        # 1-4. History + trimming + important preservation (reuse frozen M1).
        conv_ctx = self.conversation_service.build_context(
            conversation.conversation_id, max_messages=self.config.max_history_messages
        )

        # 5. Inject founder memory (M6) -- fail closed.
        memory_items, memory_ok = self._safe_memory(conversation.founder_id)

        # 6. Inject retrieval (M3), queried by the current message -- fail closed.
        retrieval, retrieval_ok = self._safe_retrieval(ally_context, current_message)

        # 7. Inject graph expansion (M4) -- fail closed.
        graph, graph_ok = self._safe_graph(ally_context)

        # 8. Include the current message, folding recent history into the text.
        founder_message = self._compose_message(conv_ctx, current_message)

        return ConversationContextWindow(
            request=GroundingRequest(
                message=founder_message, language=language, response_category=response_category
            ),
            ally_context=ally_context,
            memory_items=memory_items,
            retrieval=retrieval,
            graph=graph,
            conversation_context=conv_ctx,
            current_message=current_message,
            memory_injected=memory_ok,
            retrieval_injected=retrieval_ok,
            graph_injected=graph_ok,
        )

    # --- fail-closed source injection ------------------------------------

    def _safe_memory(self, founder_id: int):
        try:
            result = self.memory.search(
                MemorySearchRequest(founder_id=founder_id, limit=self.config.memory_limit)
            )
            return result.items, True
        except Exception as exc:  # noqa: BLE001 -- degrade, never fail the turn
            logger.warning("ai_chat: memory injection failed; continuing",
                           extra={"stage": "inject_memory", "error": str(exc)})
            return (), False

    def _safe_retrieval(self, ally_context, query: str):
        try:
            return self.retrieval.retrieve(ally_context, query), True
        except Exception as exc:  # noqa: BLE001
            logger.warning("ai_chat: retrieval injection failed; continuing",
                           extra={"stage": "inject_retrieval", "error": str(exc)})
            return None, False

    def _safe_graph(self, ally_context):
        try:
            return self.knowledge_graph.expand_for_context(ally_context), True
        except Exception as exc:  # noqa: BLE001
            logger.warning("ai_chat: graph injection failed; continuing",
                           extra={"stage": "inject_graph", "error": str(exc)})
            return None, False

    # --- message composition ---------------------------------------------

    @staticmethod
    def _compose_message(conv_ctx: ConversationContext, current_message: str) -> str:
        """Fold the trimmed earlier turns into a transcript, then the current
        message. The current turn is the highest-sequence message (just appended),
        so everything before it is 'earlier'. First message -> just the message."""
        messages = conv_ctx.recent_messages
        earlier = messages[:-1] if messages else ()
        if not earlier:
            return current_message
        transcript = "\n".join(f"{_SPEAKER.get(m.role, 'User')}: {m.content}" for m in earlier)
        return (
            f"Earlier in this conversation:\n{transcript}\n\n"
            f"Founder's current message:\n{current_message}"
        )
