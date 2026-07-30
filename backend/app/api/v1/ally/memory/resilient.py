"""Resilience wrappers: founder memory DEGRADES, it never fails a conversation.

Memory is an ENHANCEMENT to the chat, not load-bearing. If a memory DB operation
errors mid-conversation we do NOT break the founder's chat over it. Instead we:

  1. roll back the request's session (a failed statement aborts the transaction;
     without a rollback every later query in the same request would also fail),
  2. LOG the failure with founder context and a DEGRADED marker -- never silently
     swallowed; "we tried and couldn't" must not look identical to success,
  3. continue: a write becomes a logged no-op, a read returns empty.

This keeps the deterministic MemoryService pure -- resilience lives at the repo
boundary, so callers see a store that simply never raises.
"""

from __future__ import annotations

import logging

from app.api.v1.ally.memory.repository import MemoryEventRepository, MemoryRepository
from app.api.v1.ally.memory.schemas import MemoryEvent, MemoryItem

logger = logging.getLogger("ally.memory")


class ResilientMemoryRepository(MemoryRepository):
    """Wrap a memory repository so DB failures degrade (and are logged) instead of
    breaking the conversation."""

    def __init__(self, inner: MemoryRepository, db):
        self._inner = inner
        self._db = db

    def _degrade(self, op: str, founder_id, exc: Exception) -> None:
        try:
            self._db.rollback()
        except Exception:  # pragma: no cover - rollback best-effort
            pass
        logger.warning("founder memory %s DEGRADED (founder=%s): %s", op, founder_id, exc)

    def save(self, item: MemoryItem) -> MemoryItem:
        try:
            return self._inner.save(item)
        except Exception as exc:
            self._degrade("write", item.founder_id, exc)
            return item  # degrade: the chat continues; the write was logged, not stored

    def get(self, memory_id: str) -> MemoryItem | None:
        try:
            return self._inner.get(memory_id)
        except Exception as exc:
            self._degrade("get", None, exc)
            return None

    def list_for_founder(self, founder_id: int) -> tuple[MemoryItem, ...]:
        try:
            return self._inner.list_for_founder(founder_id)
        except Exception as exc:
            self._degrade("read", founder_id, exc)
            return ()

    def delete(self, memory_id: str) -> bool:
        try:
            return self._inner.delete(memory_id)
        except Exception as exc:
            self._degrade("delete", None, exc)
            return False


class ResilientMemoryEventRepository(MemoryEventRepository):
    """Same degrade-don't-fail policy for the append-only event timeline."""

    def __init__(self, inner: MemoryEventRepository, db):
        self._inner = inner
        self._db = db

    def _degrade(self, founder_id, exc: Exception) -> None:
        try:
            self._db.rollback()
        except Exception:  # pragma: no cover
            pass
        logger.warning("founder memory EVENT DEGRADED (founder=%s): %s", founder_id, exc)

    def append(self, event: MemoryEvent) -> MemoryEvent:
        try:
            return self._inner.append(event)
        except Exception as exc:
            self._degrade(event.founder_id, exc)
            return event

    def list_for_memory(self, memory_id: str) -> tuple[MemoryEvent, ...]:
        try:
            return self._inner.list_for_memory(memory_id)
        except Exception as exc:
            self._degrade(None, exc)
            return ()

    def list_for_founder(self, founder_id: int) -> tuple[MemoryEvent, ...]:
        try:
            return self._inner.list_for_founder(founder_id)
        except Exception as exc:
            self._degrade(founder_id, exc)
            return ()
