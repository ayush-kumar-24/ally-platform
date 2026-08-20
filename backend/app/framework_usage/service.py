"""FrameworkUsageService -- the only place framework-usage business rules live.

Repository-driven and deterministic (injected clock), same pattern as
VisionService/FounderGoalService, so the hermetic test suite can assert
exact records. The API layer maps HTTP to these calls and holds no logic
of its own.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from app.framework_usage.errors import InvalidFrameworkUsageInputError
from app.framework_usage.models import FrameworkUsage
from app.framework_usage.repository import FrameworkUsageRepository

MAX_FRAMEWORK_ID_LENGTH = 64
MAX_NOTE_LENGTH = 2000


def _clean_framework_id(framework_id: str) -> str:
    framework_id = (framework_id or "").strip()
    if not framework_id:
        raise InvalidFrameworkUsageInputError("framework_id", "cannot be empty")
    if len(framework_id) > MAX_FRAMEWORK_ID_LENGTH:
        raise InvalidFrameworkUsageInputError("framework_id", f"must be {MAX_FRAMEWORK_ID_LENGTH} characters or fewer")
    return framework_id


def _clean_note(note: str | None) -> str:
    note = (note or "").strip()
    if len(note) > MAX_NOTE_LENGTH:
        raise InvalidFrameworkUsageInputError("note", f"must be {MAX_NOTE_LENGTH} characters or fewer")
    return note


class FrameworkUsageService:
    def __init__(self, repository: FrameworkUsageRepository, *, clock: Callable[[], datetime] | None = None):
        self.repository = repository
        self._now = clock or (lambda: datetime.now(timezone.utc))

    def list_usage(self, founder_id: int) -> tuple[FrameworkUsage, ...]:
        """Only frameworks this founder has actually opened -- unlike Vision's
        fixed six territories, the set of frameworks is open-ended and
        frontend-owned, so there's no known list to fill empty placeholders
        for. The frontend already treats a missing id as "not used yet"."""
        return self.repository.list_for_founder(founder_id)

    def record_used(self, founder_id: int, framework_id: str, *, at: datetime | None = None) -> FrameworkUsage:
        """Called when the founder opens a framework's detail page -- the one
        honest signal available. Idempotent-ish: bumps last_used_at, keeps
        any existing note untouched."""
        framework_id = _clean_framework_id(framework_id)
        existing = self.repository.get(founder_id, framework_id)
        usage = FrameworkUsage(
            founder_id=founder_id,
            framework_id=framework_id,
            last_used_at=at or self._now(),
            note=existing.note if existing else "",
        )
        return self.repository.upsert(usage)

    def save_note(self, founder_id: int, framework_id: str, note: str) -> FrameworkUsage:
        """Empty/whitespace-only note clears it (matches services/
        frameworks.js's saveNote(), which deletes the map entry on blank
        text). If somehow called before record_used ever ran for this
        framework, last_used_at is stamped now rather than left null --
        writing a note about a framework is itself evidence of having
        engaged with it."""
        framework_id = _clean_framework_id(framework_id)
        existing = self.repository.get(founder_id, framework_id)
        usage = FrameworkUsage(
            founder_id=founder_id,
            framework_id=framework_id,
            last_used_at=existing.last_used_at if existing else self._now(),
            note=_clean_note(note),
        )
        return self.repository.upsert(usage)


def build_framework_usage_service(
    repository: FrameworkUsageRepository | None = None, *, clock: Callable[[], datetime] | None = None,
) -> FrameworkUsageService:
    """Factory. Defaults to the in-memory repository (tests/offline)."""
    from app.framework_usage.repository import InMemoryFrameworkUsageRepository

    return FrameworkUsageService(repository or InMemoryFrameworkUsageRepository(), clock=clock)
