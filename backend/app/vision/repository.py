"""Vision persistence seam.

`VisionRepository` is the interface the service depends on. Two
implementations: InMemoryVisionRepository (deterministic, thread-safe, used
by tests) and SqlAlchemyVisionRepository (db_repository.py, production).
Mirrors app/founder_goals/repository.py's shape, split across two small
tables (territories, summary) instead of one.
"""

from __future__ import annotations

import abc
import threading

from app.vision.models import VisionSummary, VisionTerritory


class VisionRepository(abc.ABC):
    @abc.abstractmethod
    def get_territory(self, founder_id: int, territory: str) -> VisionTerritory | None: ...

    @abc.abstractmethod
    def list_territories(self, founder_id: int) -> tuple[VisionTerritory, ...]: ...

    @abc.abstractmethod
    def upsert_territory(self, territory: VisionTerritory) -> VisionTerritory: ...

    @abc.abstractmethod
    def get_summary(self, founder_id: int) -> VisionSummary | None: ...

    @abc.abstractmethod
    def upsert_summary(self, summary: VisionSummary) -> VisionSummary: ...


class InMemoryVisionRepository(VisionRepository):
    def __init__(self) -> None:
        self._territories: dict[tuple[int, str], VisionTerritory] = {}
        self._summaries: dict[int, VisionSummary] = {}
        self._lock = threading.RLock()

    def get_territory(self, founder_id: int, territory: str) -> VisionTerritory | None:
        with self._lock:
            return self._territories.get((founder_id, territory))

    def list_territories(self, founder_id: int) -> tuple[VisionTerritory, ...]:
        with self._lock:
            items = [t for (fid, _key), t in self._territories.items() if fid == founder_id]
        items.sort(key=lambda t: t.territory)
        return tuple(items)

    def upsert_territory(self, territory: VisionTerritory) -> VisionTerritory:
        with self._lock:
            self._territories[(territory.founder_id, territory.territory)] = territory
        return territory

    def get_summary(self, founder_id: int) -> VisionSummary | None:
        with self._lock:
            return self._summaries.get(founder_id)

    def upsert_summary(self, summary: VisionSummary) -> VisionSummary:
        with self._lock:
            self._summaries[summary.founder_id] = summary
        return summary
