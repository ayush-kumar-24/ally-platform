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
        self, founder_id: int, *, statuses: tuple[ConversationStatus, ...]
    ) -> tuple[Conversation, ...]: ...

    @abc.abstractmethod
    def purge_conversation(self, conversation_id: str) -> bool:
        """Hard-remove a conversation and its messages/summary. Distinct from the
        service's soft delete (which only sets status=DELETED)."""

    # --- messages --------------------------------------------------------
    @abc.abstractmethod
    def add_message(self, message: ConversationMessage) -> None: ...

    @abc.abstractmethod
    def list_messages(self, conversation_id: str) -> tuple[ConversationMessage, ...]: ...

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
        self, founder_id: int, *, statuses: tuple[ConversationStatus, ...]
    ) -> tuple[Conversation, ...]:
        with self._lock:
            found = [
                c for c in self._conversations.values()
                if c.founder_id == founder_id and c.status in statuses
            ]
        # Deterministic: newest activity first, then id as a stable tiebreak.
        found.sort(key=lambda c: (c.last_message_at or c.created_at, c.conversation_id), reverse=True)
        return tuple(found)

    def purge_conversation(self, conversation_id: str) -> bool:
        with self._lock:
            existed = self._conversations.pop(conversation_id, None) is not None
            self._messages.pop(conversation_id, None)
            self._summaries.pop(conversation_id, None)
            return existed

    # --- messages --------------------------------------------------------

    def add_message(self, message: ConversationMessage) -> None:
        with self._lock:
            self._messages.setdefault(message.conversation_id, []).append(message)

    def list_messages(self, conversation_id: str) -> tuple[ConversationMessage, ...]:
        with self._lock:
            msgs = list(self._messages.get(conversation_id, ()))
        msgs.sort(key=lambda m: m.sequence)
        return tuple(msgs)

    # --- summaries -------------------------------------------------------

    def save_summary(self, summary: ConversationSummary) -> None:
        with self._lock:
            self._summaries[summary.conversation_id] = summary

    def get_summary(self, conversation_id: str) -> ConversationSummary | None:
        with self._lock:
            return self._summaries.get(conversation_id)
