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
from dataclasses import replace

from app.vision.models import VisionSummary, VisionTerritory


class VisionRepository(abc.ABC):
    @abc.abstractmethod
    def get_territory(self, founder_id: int, territory: str) -> VisionTerritory | None: ...

    @abc.abstractmethod
    def list_territories(self, founder_id: int) -> tuple[VisionTerritory, ...]: ...

    @abc.abstractmethod
    def upsert_territory(self, territory: VisionTerritory) -> VisionTerritory: ...

    @abc.abstractmethod
    def set_territory_image(
        self, founder_id: int, territory: str, *, image_url: str | None, storage_path: str | None,
    ) -> VisionTerritory | None: ...

    def get_territory_storage_path(self, founder_id: int, territory: str) -> str | None: ...

    def get_summary(self, founder_id: int) -> VisionSummary | None: ...

    @abc.abstractmethod
    def upsert_summary(self, summary: VisionSummary) -> VisionSummary: ...


class InMemoryVisionRepository(VisionRepository):
    def __init__(self) -> None:
        self._territories: dict[tuple[int, str], VisionTerritory] = {}
        self._summaries: dict[int, VisionSummary] = {}
        # Kept beside the territory rather than on it: storage_path is an
        # operational detail of where bytes live, never something the API
        # returns, so it has no business on the domain object.
        self._storage_paths: dict[tuple[int, str], str | None] = {}
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
        """Text only -- an existing picture survives a statement edit.

        The SQL repository gets this for free by simply not assigning the image
        columns. Here the whole object is replaced, so the carry-over has to be
        explicit; without it this fake would pass tests that production fails,
        which is the one thing a fake must never do.
        """
        key = (territory.founder_id, territory.territory)
        with self._lock:
            existing = self._territories.get(key)
            stored = replace(territory, image_url=existing.image_url if existing else territory.image_url)
            self._territories[key] = stored
        return stored

    def set_territory_image(
        self, founder_id: int, territory: str, *, image_url: str | None, storage_path: str | None,
    ) -> VisionTerritory | None:
        key = (founder_id, territory)
        with self._lock:
            existing = self._territories.get(key)
            if existing is None:
                return None
            updated = replace(existing, image_url=image_url)
            self._territories[key] = updated
            self._storage_paths[key] = storage_path
        return updated

    def get_territory_storage_path(self, founder_id: int, territory: str) -> str | None:
        with self._lock:
            return self._storage_paths.get((founder_id, territory))

    def get_summary(self, founder_id: int) -> VisionSummary | None:
        with self._lock:
            return self._summaries.get(founder_id)

    def upsert_summary(self, summary: VisionSummary) -> VisionSummary:
        with self._lock:
            self._summaries[summary.founder_id] = summary
        return summary
