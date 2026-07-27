"""Memory persistence. Loading and saving only -- no policy, no filtering logic.

Search/classification/lifecycle decisions live in the service and policy; the
repository just stores and returns items by id or founder. This is the seam a
future durable adapter (Postgres, Redis, or a vector store for semantic recall)
implements without changing the service.
"""

from __future__ import annotations

import abc
from collections.abc import Iterable

from app.api.v1.ally.memory.schemas import MemoryEvent, MemoryItem


class MemoryRepository(abc.ABC):
    @abc.abstractmethod
    def save(self, item: MemoryItem) -> MemoryItem:
        """Insert or replace by memory_id (upsert). Persistence only."""
        raise NotImplementedError

    @abc.abstractmethod
    def get(self, memory_id: str) -> MemoryItem | None:
        raise NotImplementedError

    @abc.abstractmethod
    def list_for_founder(self, founder_id: int) -> tuple[MemoryItem, ...]:
        raise NotImplementedError

    @abc.abstractmethod
    def delete(self, memory_id: str) -> bool:
        raise NotImplementedError


class InMemoryMemoryRepository(MemoryRepository):
    """Offline dict-backed store. Source of truth for tests; also valid for a
    small in-process cache."""

    def __init__(self, items: Iterable[MemoryItem] = ()):
        self._items: dict[str, MemoryItem] = {i.memory_id: i for i in items}

    def save(self, item: MemoryItem) -> MemoryItem:
        self._items[item.memory_id] = item
        return item

    def get(self, memory_id: str) -> MemoryItem | None:
        return self._items.get(memory_id)

    def list_for_founder(self, founder_id: int) -> tuple[MemoryItem, ...]:
        return tuple(i for i in self._items.values() if i.founder_id == founder_id)

    def delete(self, memory_id: str) -> bool:
        return self._items.pop(memory_id, None) is not None


class MemoryEventRepository(abc.ABC):
    """Append-only store of memory domain events. Events are never updated or
    deleted -- the ordered sequence IS the timeline."""

    @abc.abstractmethod
    def append(self, event: MemoryEvent) -> MemoryEvent:
        raise NotImplementedError

    @abc.abstractmethod
    def list_for_memory(self, memory_id: str) -> tuple[MemoryEvent, ...]:
        raise NotImplementedError

    @abc.abstractmethod
    def list_for_founder(self, founder_id: int) -> tuple[MemoryEvent, ...]:
        raise NotImplementedError


class InMemoryMemoryEventRepository(MemoryEventRepository):
    """Offline append-only event log. Insertion order is chronological (the clock
    only moves forward), so it is also the deterministic timeline order."""

    def __init__(self, events: Iterable[MemoryEvent] = ()):
        self._events: list[MemoryEvent] = list(events)

    def append(self, event: MemoryEvent) -> MemoryEvent:
        self._events.append(event)
        return event

    def list_for_memory(self, memory_id: str) -> tuple[MemoryEvent, ...]:
        return tuple(e for e in self._events if e.memory_id == memory_id)

    def list_for_founder(self, founder_id: int) -> tuple[MemoryEvent, ...]:
        return tuple(e for e in self._events if e.founder_id == founder_id)
