"""AchievementService -- the only place achievement business rules live.

Repository-driven and deterministic (injected clock + id factory), same
pattern as every other service in this codebase. The API layer maps HTTP to
these calls and holds no logic of its own.

Two things worth knowing:

1. Ownership check: update/delete treat "exists but belongs to someone
   else" identically to "doesn't exist" (404, not 403) -- so a founder
   probing another founder's achievement_id learns nothing. Same convention
   as FounderGoalService/PlanningService.
2. The engagement gate is enforced HERE, not just hidden in the frontend --
   `create_achievement` raises AchievementsLockedError if the founder hasn't
   talked to Ally enough yet (see UNLOCK_MESSAGE_THRESHOLD). A UI gate alone
   would let a founder call POST /achievements directly and bypass it; this
   codebase already treats that as a real bug elsewhere (see
   app/api/v1/planning/dependencies.py's require_plan_your_day docstring:
   "A UI gate is not an entitlement"). Reading and editing/deleting an
   already-created achievement is NOT gated -- once legitimately created,
   it's the founder's own record regardless of what their engagement looks
   like later.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Callable

from app.achievements.errors import (
    AchievementNotFoundError,
    AchievementsLockedError,
    InvalidAchievementInputError,
)
from app.achievements.models import Achievement, Engagement
from app.achievements.repository import AchievementRepository

MAX_TITLE_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 1000
MAX_CATEGORY_LENGTH = 50
MAX_OCCURRED_ON_LENGTH = 50

# Total messages across all of a founder's conversations with Ally is the
# honest stand-in for "how much Ally has to work with" until a real
# achievement-detection feature exists. Mirrors the frontend's own constant
# (services/achievements.js) -- this is now the source of truth; the
# frontend reads it back from GET /achievements/engagement instead of
# hardcoding its own copy.
UNLOCK_MESSAGE_THRESHOLD = 15


def _clean_title(title: str) -> str:
    title = title.strip()
    if not title:
        raise InvalidAchievementInputError("title", "cannot be empty")
    if len(title) > MAX_TITLE_LENGTH:
        raise InvalidAchievementInputError("title", f"must be {MAX_TITLE_LENGTH} characters or fewer")
    return title


def _clean(value: str | None, field: str, max_len: int) -> str:
    value = (value or "").strip()
    if len(value) > max_len:
        raise InvalidAchievementInputError(field, f"must be {max_len} characters or fewer")
    return value


class AchievementService:
    def __init__(
        self,
        repository: AchievementRepository,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
        unlock_threshold: int = UNLOCK_MESSAGE_THRESHOLD,
    ):
        self.repository = repository
        self._now = clock or (lambda: datetime.now(timezone.utc))
        self._new_id = id_factory or (lambda: uuid.uuid4().hex)
        self._unlock_threshold = unlock_threshold

    def get_engagement(self, founder_id: int) -> Engagement:
        return Engagement(
            message_count=self.repository.total_messages(founder_id),
            threshold=self._unlock_threshold,
        )

    def create_achievement(
        self, founder_id: int, *,
        title: str, description: str = "", category: str = "", occurred_on: str = "",
    ) -> Achievement:
        if not self.get_engagement(founder_id).unlocked:
            raise AchievementsLockedError()

        now = self._now()
        achievement = Achievement(
            achievement_id=self._new_id(),
            founder_id=founder_id,
            title=_clean_title(title),
            description=_clean(description, "description", MAX_DESCRIPTION_LENGTH),
            category=_clean(category, "category", MAX_CATEGORY_LENGTH),
            occurred_on=_clean(occurred_on, "occurred_on", MAX_OCCURRED_ON_LENGTH),
            created_at=now,
            updated_at=now,
        )
        return self.repository.add(achievement)

    def list_achievements(self, founder_id: int) -> tuple[Achievement, ...]:
        return self.repository.list_for_founder(founder_id)

    def update_achievement(
        self, founder_id: int, achievement_id: str, *,
        title: str | None = None, description: str | None = None,
        category: str | None = None, occurred_on: str | None = None,
    ) -> Achievement:
        existing = self.repository.get(achievement_id)
        if existing is None or existing.founder_id != founder_id:
            raise AchievementNotFoundError(achievement_id)

        updated = Achievement(
            achievement_id=existing.achievement_id,
            founder_id=existing.founder_id,
            title=_clean_title(title) if title is not None else existing.title,
            description=_clean(description, "description", MAX_DESCRIPTION_LENGTH)
                if description is not None else existing.description,
            category=_clean(category, "category", MAX_CATEGORY_LENGTH)
                if category is not None else existing.category,
            occurred_on=_clean(occurred_on, "occurred_on", MAX_OCCURRED_ON_LENGTH)
                if occurred_on is not None else existing.occurred_on,
            created_at=existing.created_at,
            updated_at=self._now(),
        )
        return self.repository.replace(updated)

    def delete_achievement(self, founder_id: int, achievement_id: str) -> None:
        existing = self.repository.get(achievement_id)
        if existing is None or existing.founder_id != founder_id:
            raise AchievementNotFoundError(achievement_id)
        self.repository.delete(achievement_id)


def build_achievement_service(
    repository: AchievementRepository | None = None,
    *,
    clock: Callable[[], datetime] | None = None,
    id_factory: Callable[[], str] | None = None,
    unlock_threshold: int = UNLOCK_MESSAGE_THRESHOLD,
) -> AchievementService:
    """Factory. Defaults to the in-memory repository (tests/offline)."""
    from app.achievements.repository import InMemoryAchievementRepository

    return AchievementService(repository or InMemoryAchievementRepository(),
                              clock=clock, id_factory=id_factory, unlock_threshold=unlock_threshold)
