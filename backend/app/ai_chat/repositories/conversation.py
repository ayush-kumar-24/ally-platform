"""Conversation persistence seam.

`ConversationRepository` is the interface the service depends on; swapping the
in-memory store for a DB-backed one (SQLAlchemy, later) is a repository
replacement only -- no service change. The in-memory implementation is
thread-safe so concurrent chats are exercised honestly in tests.
"""

from __future__ import annotations

import abc
import threading

from app.ai_chat.schemas.conversation import (
    Conversation,
    ConversationMessage,
    ConversationStatus,
    ConversationSummary,
)


class ConversationRepository(abc.ABC):
    # --- conversations ---------------------------------------------------
    @abc.abstractmethod
    def add_conversation(self, conversation: Conversation) -> None: ...

    @abc.abstractmethod
    def get_conversation(self, conversation_id: str) -> Conversation | None: ...

    @abc.abstractmethod
    def replace_conversation(self, conversation: Conversation) -> None: ...

    @abc.abstractmethod
    def list_conversations(
        self, founder_id: int, *, statuses: tuple[ConversationStatus, ...],
        limit: int | None = None, offset: int = 0,
    ) -> tuple[Conversation, ...]:
        """Newest activity first. `limit=None` means every match, which is the
        historical behaviour and what the summarise/export paths still want.

        Paging is opt-in rather than a default because this used to have no
        ceiling at all: opening the chat page read every conversation a founder
        had ever started, and the transcript read every message in it. That is
        fine at twenty and not at two thousand, and the cost lands on the
        founders who use Ally most."""

    def count_conversations(
        self, founder_id: int, *, statuses: tuple[ConversationStatus, ...]
    ) -> int:
        """How many match, ignoring paging -- so a caller can say "12 of 340".

        Concrete, not abstract: the generic answer below is correct for any
        implementation, and a store that can count more cheaply than it can
        materialise (SQL can) overrides it. Making it abstract would break
        every existing implementation for no gain."""
        return len(self.list_conversations(founder_id, statuses=statuses))

    @abc.abstractmethod
    def purge_conversation(self, conversation_id: str) -> bool:
        """Hard-remove a conversation and its messages/summary. Distinct from the
        service's soft delete (which only sets status=DELETED)."""

    # --- messages --------------------------------------------------------
    @abc.abstractmethod
    def add_message(self, message: ConversationMessage) -> str | None:
        """Persist a message; return the id it is actually stored under.

        A SQL-backed store assigns its own key, which is what every later
        read will report -- returning it lets the service correct the id it
        minted, so a message written and then read back has ONE identity.
        None means 'the id you gave me is the one I kept'."""
        ...

    @abc.abstractmethod
    def list_messages(
        self, conversation_id: str, *, limit: int | None = None, offset: int | None = None,
    ) -> tuple[ConversationMessage, ...]:
        """Oldest first. `limit=None` returns the whole transcript.

        With `limit` set and no `offset`, the window is the LAST `limit`
        messages, not the first -- a transcript is read from the bottom, so the
        newest page is the one worth loading. Pass `offset` explicitly to walk
        backwards from there.

        `sequence` on every returned message stays position-in-conversation,
        never position-in-page. Anything keyed to it (attachments, retry
        matching) would otherwise silently point at the wrong turn once a
        conversation grew past one page."""

    def count_messages(self, conversation_id: str) -> int:
        """Total messages, ignoring paging. Concrete for the same reason as
        `count_conversations` above."""
        return len(self.list_messages(conversation_id))

    @abc.abstractmethod
    def find_messages_by_request_id(
        self, conversation_id: str, request_id: str,
    ) -> tuple[ConversationMessage, ...]:
        """Messages tagged with this request_id in this conversation -- at most
        one user + one assistant message, since both halves of a turn share the
        id (see ChatExecutionService.send_message). Used to make a retried
        send_message idempotent instead of duplicating the turn."""

    # --- summaries -------------------------------------------------------
    @abc.abstractmethod
    def save_summary(self, summary: ConversationSummary) -> None: ...

    @abc.abstractmethod
    def get_summary(self, conversation_id: str) -> ConversationSummary | None: ...


class InMemoryConversationRepository(ConversationRepository):
    """Process-local, thread-safe store. Deterministic ordering on every read."""

    def __init__(self) -> None:
        self._conversations: dict[str, Conversation] = {}
        self._messages: dict[str, list[ConversationMessage]] = {}
        self._summaries: dict[str, ConversationSummary] = {}
        self._lock = threading.RLock()

    # --- conversations ---------------------------------------------------

    def add_conversation(self, conversation: Conversation) -> None:
        with self._lock:
            self._conversations[conversation.conversation_id] = conversation
            self._messages.setdefault(conversation.conversation_id, [])

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        with self._lock:
            return self._conversations.get(conversation_id)

    def replace_conversation(self, conversation: Conversation) -> None:
        with self._lock:
            self._conversations[conversation.conversation_id] = conversation

    def list_conversations(
        self, founder_id: int, *, statuses: tuple[ConversationStatus, ...],
        limit: int | None = None, offset: int = 0,
    ) -> tuple[Conversation, ...]:
        with self._lock:
            found = [
                c for c in self._conversations.values()
                if c.founder_id == founder_id and c.status in statuses
            ]
        # Deterministic: newest activity first, then id as a stable tiebreak.
        found.sort(key=lambda c: (c.last_message_at or c.created_at, c.conversation_id), reverse=True)
        # Slicing AFTER the sort, so a page is a window on the same order the
        # unpaged call returns -- paging that reordered its own results would
        # let a conversation appear on two pages and never on a third.
        start = max(0, offset)
        return tuple(found[start:] if limit is None else found[start:start + limit])

    def count_conversations(
        self, founder_id: int, *, statuses: tuple[ConversationStatus, ...]
    ) -> int:
        with self._lock:
            return sum(
                1 for c in self._conversations.values()
                if c.founder_id == founder_id and c.status in statuses
            )

    def purge_conversation(self, conversation_id: str) -> bool:
        with self._lock:
            existed = self._conversations.pop(conversation_id, None) is not None
            self._messages.pop(conversation_id, None)
            self._summaries.pop(conversation_id, None)
            return existed

    # --- messages --------------------------------------------------------

    def add_message(self, message: ConversationMessage) -> str | None:
        with self._lock:
            self._messages.setdefault(message.conversation_id, []).append(message)
        return None  # in-memory keeps the minted id verbatim

    def list_messages(
        self, conversation_id: str, *, limit: int | None = None, offset: int | None = None,
    ) -> tuple[ConversationMessage, ...]:
        with self._lock:
            msgs = list(self._messages.get(conversation_id, ()))
        msgs.sort(key=lambda m: m.sequence)
        if limit is None:
            return tuple(msgs) if offset is None else tuple(msgs[max(0, offset):])
        # No offset means "the newest page", so start `limit` from the end.
        start = max(0, len(msgs) - limit) if offset is None else max(0, offset)
        return tuple(msgs[start:start + limit])

    def count_messages(self, conversation_id: str) -> int:
        with self._lock:
            return len(self._messages.get(conversation_id, ()))

    def find_messages_by_request_id(
        self, conversation_id: str, request_id: str,
    ) -> tuple[ConversationMessage, ...]:
        with self._lock:
            msgs = list(self._messages.get(conversation_id, ()))
        matched = [m for m in msgs if (m.metadata or {}).get("request_id") == request_id]
        matched.sort(key=lambda m: m.sequence)
        return tuple(matched)

    # --- summaries -------------------------------------------------------

    def save_summary(self, summary: ConversationSummary) -> None:
        with self._lock:
            self._summaries[summary.conversation_id] = summary

    def get_summary(self, conversation_id: str) -> ConversationSummary | None:
        with self._lock:
            return self._summaries.get(conversation_id)
