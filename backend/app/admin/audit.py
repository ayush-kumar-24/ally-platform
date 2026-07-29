"""Audit logging (Phase 12, Part 5). Append-only: events are recorded, never
updated or deleted."""

from __future__ import annotations

import abc
import threading

from app.admin.models import AuditEvent


class AuditRepository(abc.ABC):
    @abc.abstractmethod
    def record(self, event: AuditEvent) -> AuditEvent:
        """Append an event. Append-only -- there is no update or delete."""

    @abc.abstractmethod
    def list(self, *, limit: int | None = 100) -> tuple[AuditEvent, ...]:
        """Most-recent first."""


class InMemoryAuditRepository(AuditRepository):
    def __init__(self) -> None:
        self._events: list[AuditEvent] = []
        self._lock = threading.RLock()

    def record(self, event: AuditEvent) -> AuditEvent:
        with self._lock:
            self._events.append(event)
        return event

    def list(self, *, limit: int | None = 100) -> tuple[AuditEvent, ...]:
        with self._lock:
            ordered = list(reversed(self._events))       # newest first
        return tuple(ordered if limit is None else ordered[:limit])
