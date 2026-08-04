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

from app.ai_chat.attachments.extraction import extract_docx_text, extract_pdf_text
from app.ai_chat.attachments.schemas import AttachmentType, SupportedMimeType
from app.ai_chat.schemas.chat import ConversationContextWindow, GroundingRequest
from app.ai_chat.schemas.conversation import Conversation, ConversationContext, MessageRole
from app.api.v1.ally.memory.schemas import MemorySearchRequest
from app.api.v1.ally.prompts.grounding.flatteners import attachments_block, tasks_block
from app.core.logger import logger
from app.planning.models import PlanStatus, ProgressStatus

_SPEAKER = {MessageRole.USER: "Founder", MessageRole.ASSISTANT: "Ally", MessageRole.SYSTEM: "System"}

# Attachment types whose bytes are decoded as plain UTF-8 text and read into the
# prompt as-is. PDF/DOCX go through dedicated extraction (extraction.py) instead --
# see _extract_text. Images are the only type nothing decodes yet (named-only).
_TEXT_READABLE = frozenset({AttachmentType.TEXT, AttachmentType.SPREADSHEET})
_EXTRACTABLE_MIME = {
    SupportedMimeType.PDF: extract_pdf_text,
    SupportedMimeType.DOCX: extract_docx_text,
}


_DEFAULT_ATTACHMENT_BYTE_BUDGET = 5_000_000  # total bytes READ+extracted per turn


class ContextWindowConfig:
    def __init__(self, *, max_history_messages: int = 20, memory_limit: int = 5,
                 attachment_limit: int = 5,
                 attachment_byte_budget: int = _DEFAULT_ATTACHMENT_BYTE_BUDGET,
                 task_limit: int = 10):
        self.max_history_messages = max_history_messages
        self.memory_limit = memory_limit
        # attachment_limit bounds how many files are even considered; byte_budget
        # additionally bounds how many of THOSE get their content read/extracted --
        # 5 files under the count cap could still be 5x25 MiB (the per-file upload
        # cap) of extraction work, so the count cap alone doesn't bound cost. Once
        # the running total exceeds the budget, remaining files fall back to
        # name-only (same as an unreadable format), never fail the turn.
        self.attachment_limit = attachment_limit
        self.attachment_byte_budget = attachment_byte_budget
        # Not-done tasks only (see _safe_tasks) -- a founder with months of
        # completed history shouldn't push their live plan out of the prompt.
        self.task_limit = task_limit


class ContextWindowBuilder:
    def __init__(
        self,
        *,
        conversation_service,
        memory,
        retrieval,
        knowledge_graph,
        attachments=None,
        planning=None,
        config: ContextWindowConfig | None = None,
    ):
        self.conversation_service = conversation_service
        self.memory = memory
        self.retrieval = retrieval
        self.knowledge_graph = knowledge_graph
        self.attachments = attachments
        self.planning = planning
        self.config = config or ContextWindowConfig()

    def build(
        self,
        *,
        ally_context,
        conversation: Conversation,
        current_message: str,
        language: str = "en",
        response_category: str = "general_chat",
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

        # 7b. Inject uploaded-file context (Milestone 4) -- fail closed. Text-
        # readable files are decoded and inlined; other types are named only.
        attachments_text, attachments_ok = self._safe_attachments(conversation.conversation_id)

        # 7c. Inject the founder's active plan/tasks (Plan Your Day) -- fail
        # closed. Not-done tasks only, so Ally can reference them mid-conversation
        # ("you had 'finish the pitch deck' on your plan") without the prompt
        # accumulating months of completed history.
        tasks_text, tasks_ok = self._safe_tasks(conversation.founder_id)

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
            attachments_injected=attachments_ok,
            attachments_text=attachments_text,
            tasks_injected=tasks_ok,
            tasks_text=tasks_text,
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

    def _safe_attachments(self, conversation_id: str) -> tuple[str, bool]:
        if self.attachments is None:
            return "", False
        try:
            items = self.attachments.list_attachments(conversation_id)
            recent = items[-self.config.attachment_limit:]
            entries = []
            spent = 0
            for a in recent:
                within_budget = spent < self.config.attachment_byte_budget
                entries.append(self._read_entry(a, extract=within_budget))
                spent += a.metadata.size_bytes
            return attachments_block(tuple(entries)), True
        except Exception as exc:  # noqa: BLE001 -- degrade, never fail the turn
            logger.warning("ai_chat: attachment injection failed; continuing",
                           extra={"stage": "inject_attachments", "error": str(exc)})
            return "", False

    def _safe_tasks(self, founder_id: int) -> tuple[str, bool]:
        if self.planning is None:
            return "", False
        try:
            entries = []
            for plan in self.planning.list_plans(founder_id):
                if plan.status != PlanStatus.ACTIVE:
                    continue
                detail = self.planning.get_plan_detail(founder_id, plan.plan_id)
                for gwt in detail.goals:
                    for task in gwt.tasks:
                        if task.status == ProgressStatus.DONE:
                            continue
                        entries.append((task.title, task.status.value, task.priority.value, task.due_date))
                        if len(entries) >= self.config.task_limit:
                            break
                    if len(entries) >= self.config.task_limit:
                        break
                if len(entries) >= self.config.task_limit:
                    break
            return tasks_block(tuple(entries)), True
        except Exception as exc:  # noqa: BLE001 -- degrade, never fail the turn
            logger.warning("ai_chat: planning task injection failed; continuing",
                           extra={"stage": "inject_tasks", "error": str(exc)})
            return "", False

    def _read_entry(self, attachment, *, extract: bool) -> tuple[str, str, int, str | None]:
        meta = attachment.metadata
        text = self._extract_text(attachment) if extract else None
        return meta.filename, meta.attachment_type.value, meta.size_bytes, text

    def _extract_text(self, attachment) -> str | None:
        """Best-effort text for one attachment. Isolated per-attachment: a failure
        here (bad decode, corrupted PDF) returns None -- the caller lists the file
        by name only -- rather than dropping the whole attachments block."""
        meta = attachment.metadata
        extractor = _EXTRACTABLE_MIME.get(getattr(meta, "mime_type", None))
        is_text_readable = meta.attachment_type in _TEXT_READABLE
        if extractor is None and not is_text_readable:
            return None
        try:
            content = self.attachments.get_content(attachment.attachment_id)
            if content is None:
                return None
            if extractor is not None:
                return extractor(content)
            return content.decode("utf-8", errors="replace")
        except Exception as exc:  # noqa: BLE001 -- one bad file must not sink the turn
            logger.warning("ai_chat: attachment text extraction failed; naming only",
                            extra={"stage": "extract_attachment_text",
                                   "attachment_id": attachment.attachment_id, "error": str(exc)})
            return None

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
