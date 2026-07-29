"""Suggestion persistence seam (Phase 6, Milestone 5, Part 6).

Interface + thread-safe in-memory implementation. Stores suggestions and feedback;
a DB swap is a repository replacement only.
"""

from __future__ import annotations

import abc
import threading

from app.ai_chat.suggestions.schemas import (
    Suggestion,
    SuggestionFeedback,
    SuggestionStatus,
)


class SuggestionRepository(abc.ABC):
    @abc.abstractmethod
    def add(self, suggestion: Suggestion) -> None: ...

    @abc.abstractmethod
    def get(self, suggestion_id: str) -> Suggestion | None: ...

    @abc.abstractmethod
    def replace(self, suggestion: Suggestion) -> None: ...

    @abc.abstractmethod
    def list_for_conversation(
        self, conversation_id: str, *, statuses: tuple[SuggestionStatus, ...]
    ) -> tuple[Suggestion, ...]: ...

    @abc.abstractmethod
    def add_feedback(self, feedback: SuggestionFeedback) -> None: ...

    @abc.abstractmethod
    def list_feedback(self, suggestion_id: str) -> tuple[SuggestionFeedback, ...]: ...

    @abc.abstractmethod
    def purge(self, suggestion_id: str) -> bool: ...


class InMemorySuggestionRepository(SuggestionRepository):
    def __init__(self) -> None:
        self._items: dict[str, Suggestion] = {}
        self._feedback: dict[str, list[SuggestionFeedback]] = {}
        self._lock = threading.RLock()

    def add(self, suggestion: Suggestion) -> None:
        with self._lock:
            self._items[suggestion.suggestion_id] = suggestion

    def get(self, suggestion_id: str) -> Suggestion | None:
        with self._lock:
            return self._items.get(suggestion_id)

    def replace(self, suggestion: Suggestion) -> None:
        with self._lock:
            self._items[suggestion.suggestion_id] = suggestion

    def list_for_conversation(self, conversation_id, *, statuses):
        with self._lock:
            found = [s for s in self._items.values()
                     if s.conversation_id == conversation_id and s.status in statuses]
        # Deterministic: rank (if set) then creation time then id.
        found.sort(key=lambda s: (s.rank if s.rank is not None else 1_000_000,
                                  s.created_at, s.suggestion_id))
        return tuple(found)

    def add_feedback(self, feedback: SuggestionFeedback) -> None:
        with self._lock:
            self._feedback.setdefault(feedback.suggestion_id, []).append(feedback)

    def list_feedback(self, suggestion_id: str) -> tuple[SuggestionFeedback, ...]:
        with self._lock:
            return tuple(self._feedback.get(suggestion_id, ()))

    def purge(self, suggestion_id: str) -> bool:
        with self._lock:
            self._feedback.pop(suggestion_id, None)
            return self._items.pop(suggestion_id, None) is not None
