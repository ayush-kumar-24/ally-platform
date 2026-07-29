"""ConversationService -- the Conversation Engine (Phase 6, Milestone 1).

All conversation business logic lives here; persistence is delegated to a
ConversationRepository. Deterministic by construction: time comes from an injected
Clock and ids from an injected id_factory, so a given sequence of calls produces
byte-identical results.

State machine (fail closed):
    ACTIVE  --archive-->  ARCHIVED  --restore-->  ACTIVE
    ACTIVE  --delete -->  DELETED   --restore-->  ACTIVE
  Appending requires ACTIVE; appending to an ARCHIVED/DELETED conversation raises
  (the caller must restore first) -- no silent side effects.

This milestone composes NOTHING from Phase 5 (no memory/retrieval/graph/execution):
that is the chat-flow milestone. Here `summarize` and `build_context` are purely
deterministic (no LLM, no token estimation).
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from typing import Any, Callable, Mapping

from app.ai_chat.clock import Clock, SystemClock
from app.ai_chat.errors import (
    ConversationNotFoundError,
    InvalidConversationStateError,
    InvalidMessageError,
)
from app.ai_chat.repositories.conversation import ConversationRepository
from app.ai_chat.schemas.conversation import (
    DEFAULT_TITLE,
    Conversation,
    ConversationContext,
    ConversationMessage,
    ConversationStatus,
    ConversationSummary,
    MessageRole,
    MessageTokenUsage,
)

_ACTIVE = ConversationStatus.ACTIVE
_ARCHIVED = ConversationStatus.ARCHIVED
_DELETED = ConversationStatus.DELETED

_DEFAULT_CONTEXT_MESSAGES = 20
_TITLE_MAX = 60


class ConversationService:
    def __init__(
        self,
        repository: ConversationRepository,
        *,
        clock: Clock | None = None,
        id_factory: Callable[[], str] | None = None,
    ):
        self.repository = repository
        self.clock = clock or SystemClock()
        self._new_id = id_factory or (lambda: uuid.uuid4().hex)

    # --- create ----------------------------------------------------------

    def create_conversation(
        self, founder_id: int, *, title: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> Conversation:
        now = self.clock.now()
        conversation = Conversation(
            conversation_id=self._new_id(),
            founder_id=founder_id,
            title=(title.strip() if title and title.strip() else DEFAULT_TITLE),
            status=_ACTIVE,
            created_at=now,
            updated_at=now,
            metadata=dict(metadata or {}),
        )
        self.repository.add_conversation(conversation)
        return conversation

    # --- append ----------------------------------------------------------

    def append_message(
        self, conversation_id: str, role: MessageRole, content: str, *,
        token_usage: MessageTokenUsage | None = None, important: bool = False,
        metadata: Mapping[str, Any] | None = None,
    ) -> ConversationMessage:
        conversation = self._require(conversation_id)
        if conversation.is_deleted:
            raise InvalidConversationStateError(conversation_id, "deleted", "append to")
        if conversation.is_archived:
            raise InvalidConversationStateError(conversation_id, "archived", "append to")
        if not content or not content.strip():
            raise InvalidMessageError("content is empty")

        now = self.clock.now()
        sequence = conversation.message_count
        message = ConversationMessage(
            message_id=self._new_id(),
            conversation_id=conversation_id,
            founder_id=conversation.founder_id,
            role=role,
            content=content,
            created_at=now,
            sequence=sequence,
            token_usage=token_usage,
            important=important,
            metadata=dict(metadata or {}),
        )
        self.repository.add_message(message)

        # Unread accrues only for the founder-facing side (Ally's replies).
        unread = conversation.unread_count + (1 if role == MessageRole.ASSISTANT else 0)
        token_stats = conversation.token_stats
        if token_usage is not None:
            token_stats = token_stats.add(token_usage.prompt_tokens, token_usage.completion_tokens)

        title = conversation.title
        if title == DEFAULT_TITLE and role == MessageRole.USER:
            title = self._derive_title(content)          # deterministic auto-title from first ask

        self.repository.replace_conversation(
            self._touch(
                conversation, now, title=title, unread_count=unread,
                message_count=conversation.message_count + 1,
                last_message_at=now, token_stats=token_stats,
            )
        )
        return message

    # --- read ------------------------------------------------------------

    def get_conversation(self, conversation_id: str) -> Conversation:
        return self._require(conversation_id)

    def get_history(self, conversation_id: str) -> tuple[ConversationMessage, ...]:
        self._require(conversation_id)
        return self.repository.list_messages(conversation_id)

    def list_conversations(
        self, founder_id: int, *, include_archived: bool = False, include_deleted: bool = False,
    ) -> tuple[Conversation, ...]:
        statuses = [_ACTIVE]
        if include_archived:
            statuses.append(_ARCHIVED)
        if include_deleted:
            statuses.append(_DELETED)
        return self.repository.list_conversations(founder_id, statuses=tuple(statuses))

    def mark_read(self, conversation_id: str) -> Conversation:
        conversation = self._require(conversation_id)
        if conversation.unread_count == 0:
            return conversation
        updated = self._touch(conversation, self.clock.now(), unread_count=0)
        self.repository.replace_conversation(updated)
        return updated

    # --- lifecycle -------------------------------------------------------

    def rename_conversation(self, conversation_id: str, title: str) -> Conversation:
        conversation = self._require(conversation_id)
        clean = title.strip()
        if not clean:
            raise InvalidMessageError("title is empty")
        updated = self._touch(conversation, self.clock.now(), title=clean[:_TITLE_MAX])
        self.repository.replace_conversation(updated)
        return updated

    def archive_conversation(self, conversation_id: str) -> Conversation:
        return self._transition(conversation_id, _ARCHIVED, forbid={_DELETED}, action="archive")

    def delete_conversation(self, conversation_id: str) -> Conversation:
        # Soft delete: recoverable via restore. Hard removal is repository.purge.
        return self._transition(conversation_id, _DELETED, forbid=frozenset(), action="delete")

    def restore_conversation(self, conversation_id: str) -> Conversation:
        return self._transition(conversation_id, _ACTIVE, forbid=frozenset(), action="restore")

    # --- summarize (deterministic, no LLM) -------------------------------

    def summarize_conversation(self, conversation_id: str) -> ConversationSummary:
        conversation = self._require(conversation_id)
        messages = self.repository.list_messages(conversation_id)
        summary = ConversationSummary(
            conversation_id=conversation_id,
            founder_id=conversation.founder_id,
            summary=self._digest(messages),
            message_count=len(messages),
            covered_through_sequence=(messages[-1].sequence if messages else -1),
            generated_at=self.clock.now(),
        )
        self.repository.save_summary(summary)
        return summary

    # --- context window (deterministic truncation) -----------------------

    def build_context(
        self, conversation_id: str, *, max_messages: int = _DEFAULT_CONTEXT_MESSAGES,
    ) -> ConversationContext:
        """Deterministic context view: the most recent `max_messages`, plus any
        message flagged `important` (preserved even if older), in sequence order.
        Founder-memory injection is a later milestone."""
        conversation = self._require(conversation_id)
        messages = self.repository.list_messages(conversation_id)
        total = len(messages)

        recent = messages[-max_messages:] if max_messages > 0 else ()
        recent_ids = {m.message_id for m in recent}
        preserved = [m for m in messages if m.important and m.message_id not in recent_ids]
        selected = sorted([*preserved, *recent], key=lambda m: m.sequence)

        truncated = len(selected) < total
        summary = self.repository.get_summary(conversation_id) if truncated else None
        return ConversationContext(
            conversation=conversation,
            recent_messages=tuple(selected),
            summary=summary,
            total_messages=total,
            truncated=truncated,
        )

    # --- internals -------------------------------------------------------

    def _require(self, conversation_id: str) -> Conversation:
        conversation = self.repository.get_conversation(conversation_id)
        if conversation is None:
            raise ConversationNotFoundError(conversation_id)
        return conversation

    def _transition(
        self, conversation_id: str, target: ConversationStatus,
        *, forbid: frozenset[ConversationStatus] | set, action: str,
    ) -> Conversation:
        conversation = self._require(conversation_id)
        if conversation.status in forbid:
            raise InvalidConversationStateError(conversation_id, conversation.status.value, action)
        if conversation.status == target:
            return conversation                          # idempotent, no spurious bump
        updated = self._touch(conversation, self.clock.now(), status=target)
        self.repository.replace_conversation(updated)
        return updated

    @staticmethod
    def _touch(conversation: Conversation, now, **changes) -> Conversation:
        return replace(conversation, updated_at=now, **changes)

    @staticmethod
    def _derive_title(content: str) -> str:
        collapsed = " ".join(content.split())
        return (collapsed[: _TITLE_MAX - 1].rstrip() + "…") if len(collapsed) > _TITLE_MAX else collapsed

    @staticmethod
    def _digest(messages: tuple[ConversationMessage, ...]) -> str:
        if not messages:
            return "No messages yet."
        users = sum(1 for m in messages if m.role == MessageRole.USER)
        assistants = sum(1 for m in messages if m.role == MessageRole.ASSISTANT)
        first = messages[0].created_at.isoformat()
        last = messages[-1].created_at.isoformat()
        latest_user = next(
            (m.content for m in reversed(messages) if m.role == MessageRole.USER), None
        )
        tail = ""
        if latest_user:
            excerpt = " ".join(latest_user.split())
            excerpt = (excerpt[:117] + "…") if len(excerpt) > 118 else excerpt
            tail = f" Latest founder message: \"{excerpt}\"."
        return (
            f"{len(messages)} messages ({users} from founder, {assistants} from Ally) "
            f"from {first} to {last}.{tail}"
        )


def build_conversation_service(
    repository: ConversationRepository | None = None,
    *,
    clock: Clock | None = None,
    id_factory: Callable[[], str] | None = None,
) -> ConversationService:
    """Offline-friendly factory. Defaults to the in-memory repository; a real
    deployment injects a DB-backed one."""
    from app.ai_chat.repositories.conversation import InMemoryConversationRepository

    return ConversationService(
        repository or InMemoryConversationRepository(), clock=clock, id_factory=id_factory
    )
