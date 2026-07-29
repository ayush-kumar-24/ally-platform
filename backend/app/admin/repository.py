"""Admin persistence seams (Phase 12, Part 2).

`AdminRepository` is the read seam over existing data (founders / conversations /
feedback / usage) plus founder-status writes. `AnnouncementRepository` stores
admin-published announcements. Both have in-memory implementations (deterministic,
thread-safe, used by tests); a production adapter composes the DB founder repo and
the ai_chat container stores -- a repository replacement, no service change.
"""

from __future__ import annotations

import abc
import threading
from dataclasses import replace

from app.admin.models import (
    Announcement,
    ConversationSummary,
    FeedbackSummary,
    FounderStatus,
    FounderSummary,
    UsageMetrics,
)


class AdminRepository(abc.ABC):
    @abc.abstractmethod
    def list_founders(self, *, limit: int | None = 50, offset: int = 0) -> tuple[FounderSummary, ...]: ...

    @abc.abstractmethod
    def search_founders(self, query: str, *, limit: int = 50) -> tuple[FounderSummary, ...]: ...

    @abc.abstractmethod
    def get_founder(self, founder_id: int) -> FounderSummary | None: ...

    @abc.abstractmethod
    def set_founder_status(self, founder_id: int, status: FounderStatus) -> FounderSummary | None: ...

    @abc.abstractmethod
    def list_conversations(self, *, founder_id: int | None = None,
                           limit: int | None = 50, offset: int = 0) -> tuple[ConversationSummary, ...]: ...

    @abc.abstractmethod
    def list_feedback(self, *, limit: int | None = 50) -> tuple[FeedbackSummary, ...]: ...

    @abc.abstractmethod
    def usage_metrics(self) -> UsageMetrics: ...


class InMemoryAdminRepository(AdminRepository):
    def __init__(self, *, founders=(), conversations=(), feedback=(), usage: UsageMetrics | None = None):
        self._founders: dict[int, FounderSummary] = {f.founder_id: f for f in founders}
        self._conversations: list[ConversationSummary] = list(conversations)
        self._feedback: list[FeedbackSummary] = list(feedback)
        self._usage = usage or UsageMetrics()
        self._lock = threading.RLock()

    def list_founders(self, *, limit=50, offset=0):
        with self._lock:
            items = sorted(self._founders.values(), key=lambda f: f.founder_id)
        window = items[offset:]
        return tuple(window if limit is None else window[:limit])

    def search_founders(self, query, *, limit=50):
        q = query.strip().lower()
        with self._lock:
            matches = [f for f in self._founders.values()
                       if q in (f.full_name or "").lower() or q in (f.email or "").lower()]
        matches.sort(key=lambda f: f.founder_id)
        return tuple(matches[:limit])

    def get_founder(self, founder_id):
        with self._lock:
            return self._founders.get(founder_id)

    def set_founder_status(self, founder_id, status):
        with self._lock:
            current = self._founders.get(founder_id)
            if current is None:
                return None
            updated = replace(current, status=status)
            self._founders[founder_id] = updated
            return updated

    def list_conversations(self, *, founder_id=None, limit=50, offset=0):
        with self._lock:
            items = [c for c in self._conversations if founder_id is None or c.founder_id == founder_id]
        items.sort(key=lambda c: (c.created_at, c.conversation_id))
        window = items[offset:]
        return tuple(window if limit is None else window[:limit])

    def list_feedback(self, *, limit=50):
        with self._lock:
            items = sorted(self._feedback, key=lambda f: (f.created_at, f.feedback_id))
        return tuple(items if limit is None else items[:limit])

    def usage_metrics(self):
        return self._usage


class AnnouncementRepository(abc.ABC):
    @abc.abstractmethod
    def save(self, announcement: Announcement) -> Announcement: ...

    @abc.abstractmethod
    def list(self, *, active_only: bool = False) -> tuple[Announcement, ...]: ...


class InMemoryAnnouncementRepository(AnnouncementRepository):
    def __init__(self) -> None:
        self._items: dict[str, Announcement] = {}
        self._lock = threading.RLock()

    def save(self, announcement: Announcement) -> Announcement:
        with self._lock:
            self._items[announcement.announcement_id] = announcement
        return announcement

    def list(self, *, active_only: bool = False):
        with self._lock:
            items = [a for a in self._items.values() if a.active or not active_only]
        items.sort(key=lambda a: (a.created_at, a.announcement_id), reverse=True)
        return tuple(items)
