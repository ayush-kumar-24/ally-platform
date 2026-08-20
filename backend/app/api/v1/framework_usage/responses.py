"""Framework Usage API response models with `from_domain` mappers."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.framework_usage.models import FrameworkUsage


class FrameworkUsageResponse(BaseModel):
    framework_id: str
    last_used_at: datetime
    note: str

    @classmethod
    def from_domain(cls, u: FrameworkUsage) -> "FrameworkUsageResponse":
        return cls(framework_id=u.framework_id, last_used_at=u.last_used_at, note=u.note)


class FrameworkUsageEntry(BaseModel):
    """One entry inside the GET /frameworks/usage map -- framework_id is the
    dict key, not repeated in the value, matching the shape
    services/frameworks.js's loadLastUsed()/loadNotes() already build
    client-side (frontend/src/pages/FrameworksPage.jsx keys off f.id)."""
    last_used_at: datetime
    note: str


def usage_map_from_domain(items: tuple[FrameworkUsage, ...]) -> dict[str, FrameworkUsageEntry]:
    return {u.framework_id: FrameworkUsageEntry(last_used_at=u.last_used_at, note=u.note) for u in items}
