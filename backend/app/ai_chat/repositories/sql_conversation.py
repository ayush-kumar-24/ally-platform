"""SQL-backed ConversationRepository -- persists to `conversations` / `messages`.

Fixes the resume gap: the process-level InMemoryConversationRepository loses every
founder's chat history on restart/redeploy and cannot be shared across worker
processes. This repository is request-scoped (built per-request with the request's
DB session, mirroring the founder-memory fix) and durable.

Identity mapping: the domain (ConversationService) mints and works with STRING ids
(uuid hex) for both conversations and messages; the DB uses integer PKs internally.
  - conversations.external_id (added by migration c3e5f7a9b1d2) holds the domain
    conversation_id. The integer conversation_id stays the internal PK/FK target.
  - messages reuses its existing `id` (uuid) column as the domain message_id --
    no new column needed.

Fields the domain round-trips that the original table didn't carry (unread_count,
token_stats, metadata on conversations; `important` and the token-usage split on
messages) are persisted via the migration's new JSONB columns, or -- for message-
level `important`/token split, where a new column was not worth adding -- packed
into the existing `messages.metadata` JSONB under internal `_` keys and stripped
back out on read so callers never see them.

`sequence` (0-based, deterministic order within a conversation) has no column:
messages.message_id is a strictly-increasing integer per row, so ordering by it
and enumerating on read reproduces the same deterministic sequence the in-memory
repository produced by construction.

Summaries stay non-durable (kept in a small process-local dict here). They are an
explicitly-marked placeholder in the domain ("NOT an AI summary... a later
milestone can replace this") and fully regenerable from message history on demand
-- unlike conversations/messages, losing one on restart loses nothing a founder
would notice, so persisting them is deliberately out of scope for this fix.

FAILS LOUD, not resilient-degrade: unlike founder memory (an enhancement layered
on top of diagnosis), this repository IS the founder's message storage. A silent
degrade-and-continue here would mean "your message was sent" while it was
actually discarded -- exactly the class of bug this fix exists to close. DB
errors propagate.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai_chat.repositories.conversation import ConversationRepository
from app.ai_chat.schemas.conversation import (
    Conversation,
    ConversationMessage,
    ConversationStatus,
    ConversationSummary,
    MessageRole,
    MessageTokenUsage,
    TokenStats,
)
from app.models.partitioned import Message as MessageRow
from app.models.schema import Conversations as ConversationRow

_CONVERSATION_TYPE = "chat"
_META_IMPORTANT = "_important"
_META_TOKEN_USAGE = "_token_usage"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SqlConversationRepository(ConversationRepository):
    def __init__(self, db: Session):
        self.db = db
        # Summaries are intentionally non-durable -- see module docstring. Shared
        # across instances within the process so a summarize-then-read within the
        # same request (or process) still works; lost on restart, by design.
        self._summaries = _SUMMARY_STORE

    # --- conversations -----------------------------------------------------

    def add_conversation(self, conversation: Conversation) -> None:
        row = ConversationRow(
            founder_id=conversation.founder_id,
            conversation_type=_CONVERSATION_TYPE,
            status=conversation.status.value,
            external_id=conversation.conversation_id,
            title=conversation.title,
            message_count=conversation.message_count,
            unread_count=conversation.unread_count,
            token_stats=self._token_stats_to_dict(conversation.token_stats),
            meta_data=dict(conversation.metadata),
            last_message_at=conversation.last_message_at,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
        )
        self.db.add(row)
        self.db.flush()

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        row = self._get_row(conversation_id)
        return self._to_domain(row) if row is not None else None

    def replace_conversation(self, conversation: Conversation) -> None:
        row = self._get_row(conversation.conversation_id)
        if row is None:
            # Defensive: the service always calls add_conversation first, but a
            # replace on a row that has vanished (e.g. hard-purged concurrently)
            # must not silently no-op and hide the loss.
            raise LookupError(f"conversation {conversation.conversation_id!r} not found")
        row.status = conversation.status.value
        row.title = conversation.title
        row.message_count = conversation.message_count
        row.unread_count = conversation.unread_count
        row.token_stats = self._token_stats_to_dict(conversation.token_stats)
        row.meta_data = dict(conversation.metadata)
        row.last_message_at = conversation.last_message_at
        row.updated_at = conversation.updated_at
        self.db.flush()

    def list_conversations(
        self, founder_id: int, *, statuses: tuple[ConversationStatus, ...]
    ) -> tuple[Conversation, ...]:
        status_values = [s.value for s in statuses]
        stmt = (
            select(ConversationRow)
            .where(
                ConversationRow.founder_id == founder_id,
                ConversationRow.conversation_type == _CONVERSATION_TYPE,
                ConversationRow.status.in_(status_values),
            )
        )
        rows = self.db.execute(stmt).scalars().all()
        found = [self._to_domain(r) for r in rows]
        found.sort(key=lambda c: (c.last_message_at or c.created_at, c.conversation_id), reverse=True)
        return tuple(found)

    def purge_conversation(self, conversation_id: str) -> bool:
        row = self._get_row(conversation_id)
        if row is None:
            return False
        self.db.delete(row)  # ON DELETE CASCADE removes its messages
        self.db.flush()
        with _SUMMARY_LOCK:
            self._summaries.pop(conversation_id, None)
        return True

    # --- messages ------------------------------------------------------

    def add_message(self, message: ConversationMessage) -> None:
        conv_row = self._get_row(message.conversation_id)
        if conv_row is None:
            raise LookupError(f"conversation {message.conversation_id!r} not found")
        meta = dict(message.metadata)
        if message.important:
            meta[_META_IMPORTANT] = True
        if message.token_usage is not None:
            meta[_META_TOKEN_USAGE] = {
                "prompt_tokens": message.token_usage.prompt_tokens,
                "completion_tokens": message.token_usage.completion_tokens,
            }
        row = MessageRow(
            conversation_id=conv_row.conversation_id,
            founder_id=message.founder_id,
            role=message.role.value,
            content=message.content,
            token_count=(message.token_usage.total_tokens if message.token_usage else None),
            meta_data=meta,
            created_at=message.created_at,
        )
        self.db.add(row)
        self.db.flush()

    def list_messages(self, conversation_id: str) -> tuple[ConversationMessage, ...]:
        conv_row = self._get_row(conversation_id)
        if conv_row is None:
            return ()
        stmt = (
            select(MessageRow)
            .where(MessageRow.conversation_id == conv_row.conversation_id)
            .order_by(MessageRow.message_id.asc())
        )
        rows = self.db.execute(stmt).scalars().all()
        return tuple(
            self._message_to_domain(r, conversation_id, sequence)
            for sequence, r in enumerate(rows)
        )

    # --- summaries (non-durable -- see module docstring) --------------------

    def save_summary(self, summary: ConversationSummary) -> None:
        with _SUMMARY_LOCK:
            self._summaries[summary.conversation_id] = summary

    def get_summary(self, conversation_id: str) -> ConversationSummary | None:
        with _SUMMARY_LOCK:
            return self._summaries.get(conversation_id)

    # --- mapping helpers -----------------------------------------------

    def _get_row(self, conversation_id: str) -> ConversationRow | None:
        return self.db.execute(
            select(ConversationRow).where(ConversationRow.external_id == conversation_id)
        ).scalar_one_or_none()

    @staticmethod
    def _token_stats_to_dict(stats: TokenStats) -> dict:
        return {
            "prompt_tokens": stats.prompt_tokens,
            "completion_tokens": stats.completion_tokens,
            "total_tokens": stats.total_tokens,
        }

    @staticmethod
    def _token_stats_from_dict(data: dict | None) -> TokenStats:
        data = data or {}
        return TokenStats(
            prompt_tokens=int(data.get("prompt_tokens", 0)),
            completion_tokens=int(data.get("completion_tokens", 0)),
            total_tokens=int(data.get("total_tokens", 0)),
        )

    def _to_domain(self, row: ConversationRow) -> Conversation:
        return Conversation(
            conversation_id=row.external_id,
            founder_id=row.founder_id,
            title=row.title or "",
            status=ConversationStatus(row.status),
            created_at=row.created_at,
            updated_at=row.updated_at,
            last_message_at=row.last_message_at,
            message_count=row.message_count,
            unread_count=row.unread_count,
            token_stats=self._token_stats_from_dict(row.token_stats),
            metadata=dict(row.meta_data or {}),
        )

    @staticmethod
    def _message_to_domain(row: MessageRow, conversation_id: str, sequence: int) -> ConversationMessage:
        meta = dict(row.meta_data or {})
        important = bool(meta.pop(_META_IMPORTANT, False))
        usage_raw = meta.pop(_META_TOKEN_USAGE, None)
        token_usage = (
            MessageTokenUsage(
                prompt_tokens=int(usage_raw.get("prompt_tokens", 0)),
                completion_tokens=int(usage_raw.get("completion_tokens", 0)),
            )
            if usage_raw is not None
            else None
        )
        return ConversationMessage(
            message_id=str(row.message_id),
            conversation_id=conversation_id,
            founder_id=row.founder_id,
            role=MessageRole(row.role),
            content=row.content,
            created_at=row.created_at,
            sequence=sequence,
            token_usage=token_usage,
            important=important,
            metadata=meta,
        )


# Process-local, not request-scoped: summaries are a regenerable cache (see module
# docstring), so sharing across requests within the process is harmless and lets a
# summarize-then-read round-trip within the same process without a DB table.
_SUMMARY_STORE: dict[str, ConversationSummary] = {}
_SUMMARY_LOCK = threading.RLock()
