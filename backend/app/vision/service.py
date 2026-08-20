"""VisionService -- the only place vision business rules live.

Repository-driven and deterministic (injected clock), same pattern as
FounderGoalService/AchievementService, so the hermetic test suite can assert
exact records. The API layer maps HTTP to these calls and holds no logic of
its own.

No ownership-mismatch case to worry about here (unlike Goals/Achievements):
every operation is scoped by founder_id from the URL/token, never by a
caller-supplied territory/summary row id, so there's nothing to probe.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from app.vision.errors import InvalidVisionInputError, InvalidVisionTerritoryError
from app.vision.models import TERRITORY_KEYS, VisionSummary, VisionTerritory
from app.vision.repository import VisionRepository

MAX_STATEMENT_LENGTH = 1000
MAX_TAG_LENGTH = 100
MAX_SUMMARY_FIELD_LENGTH = 100


def _clean_statement(statement: str) -> str:
    statement = (statement or "").strip()
    if not statement:
        raise InvalidVisionInputError("statement", "cannot be empty")
    if len(statement) > MAX_STATEMENT_LENGTH:
        raise InvalidVisionInputError("statement", f"must be {MAX_STATEMENT_LENGTH} characters or fewer")
    return statement


def _clean_tag(value: str | None, field: str) -> str:
    value = (value or "").strip()
    if len(value) > MAX_TAG_LENGTH:
        raise InvalidVisionInputError(field, f"must be {MAX_TAG_LENGTH} characters or fewer")
    return value


def _clean_summary_field(value: str | None, field: str) -> str:
    value = (value or "").strip()
    if len(value) > MAX_SUMMARY_FIELD_LENGTH:
        raise InvalidVisionInputError(field, f"must be {MAX_SUMMARY_FIELD_LENGTH} characters or fewer")
    return value


class VisionService:
    def __init__(self, repository: VisionRepository, *, clock: Callable[[], datetime] | None = None):
        self.repository = repository
        self._now = clock or (lambda: datetime.now(timezone.utc))

    def get_territories(self, founder_id: int) -> dict[str, VisionTerritory | None]:
        """All six territories, keyed by TERRITORY_KEYS order. A key maps to
        None when the founder hasn't written that one yet -- the API layer
        turns that into an empty {statement:'', tag1:'', tag2:''}, never a
        fabricated statement."""
        existing = {t.territory: t for t in self.repository.list_territories(founder_id)}
        return {key: existing.get(key) for key in TERRITORY_KEYS}

    def upsert_territory(
        self, founder_id: int, territory_key: str, *, statement: str, tag1: str = "", tag2: str = "",
    ) -> VisionTerritory:
        if territory_key not in TERRITORY_KEYS:
            raise InvalidVisionTerritoryError(territory_key)
        vt = VisionTerritory(
            founder_id=founder_id,
            territory=territory_key,
            statement=_clean_statement(statement),
            tag1=_clean_tag(tag1, "tag1"),
            tag2=_clean_tag(tag2, "tag2"),
            updated_at=self._now(),
        )
        return self.repository.upsert_territory(vt)

    def get_summary(self, founder_id: int) -> VisionSummary | None:
        """None when the founder hasn't written a summary yet -- the API
        layer turns that into empty fields, same convention as territories."""
        return self.repository.get_summary(founder_id)

    def upsert_summary(
        self, founder_id: int, *,
        target: str | None = None, current: str | None = None, unit: str | None = None,
    ) -> VisionSummary:
        """Partial update: an omitted (None) field keeps its previous value,
        matching FounderGoalService.update_goal's convention. A field passed
        as '' is a deliberate clear, not a no-op."""
        existing = self.repository.get_summary(founder_id)
        vs = VisionSummary(
            founder_id=founder_id,
            target=_clean_summary_field(target, "target") if target is not None
                   else (existing.target if existing else ""),
            current=_clean_summary_field(current, "current") if current is not None
                    else (existing.current if existing else ""),
            unit=_clean_summary_field(unit, "unit") if unit is not None
                 else (existing.unit if existing else ""),
            updated_at=self._now(),
        )
        return self.repository.upsert_summary(vs)


def build_vision_service(
    repository: VisionRepository | None = None, *, clock: Callable[[], datetime] | None = None,
) -> VisionService:
    """Factory. Defaults to the in-memory repository (tests/offline)."""
    from app.vision.repository import InMemoryVisionRepository

    return VisionService(repository or InMemoryVisionRepository(), clock=clock)
