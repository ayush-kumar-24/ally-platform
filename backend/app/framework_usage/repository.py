"""Framework Usage persistence seam.

`FrameworkUsageRepository` is the interface the service depends on. Two
implementations: InMemoryFrameworkUsageRepository (deterministic,
thread-safe, used by tests) and SqlAlchemyFrameworkUsageRepository
(db_repository.py, production). Mirrors app/vision/repository.py's shape.
"""

from __future__ import annotations

import abc
import threading

from app.framework_usage.models import FrameworkUsage


class FrameworkUsageRepository(abc.ABC):
    @abc.abstractmethod
    def get(self, founder_id: int, framework_id: str) -> FrameworkUsage | None: ...

    @abc.abstractmethod
    def list_for_founder(self, founder_id: int) -> tuple[FrameworkUsage, ...]: ...

    @abc.abstractmethod
    def upsert(self, usage: FrameworkUsage) -> FrameworkUsage: ...


class InMemoryFrameworkUsageRepository(FrameworkUsageRepository):
    def __init__(self) -> None:
        self._rows: dict[tuple[int, str], FrameworkUsage] = {}
        self._lock = threading.RLock()

    def get(self, founder_id: int, framework_id: str) -> FrameworkUsage | None:
        with self._lock:
            return self._rows.get((founder_id, framework_id))

    def list_for_founder(self, founder_id: int) -> tuple[FrameworkUsage, ...]:
        with self._lock:
            items = [u for (fid, _key), u in self._rows.items() if fid == founder_id]
        items.sort(key=lambda u: u.last_used_at, reverse=True)
        return tuple(items)

    def upsert(self, usage: FrameworkUsage) -> FrameworkUsage:
        with self._lock:
            self._rows[(usage.founder_id, usage.framework_id)] = usage
        return usage
