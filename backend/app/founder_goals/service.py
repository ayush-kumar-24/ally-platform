"""FounderGoalService -- the only place founder-goal business rules live.

Repository-driven and deterministic (injected clock + id factory), same
pattern as ConsentService/PlanningService, so the hermetic test suite can
assert exact records. The API layer maps HTTP to these calls and holds no
logic of its own.

Ownership check: get/update/delete treat "exists but belongs to someone
else" identically to "doesn't exist" (404, not 403) -- so a founder probing
another founder's goal_id learns nothing about whether it exists. Same
convention as PlanningService.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Callable

from app.founder_goals.errors import FounderGoalNotFoundError, InvalidFounderGoalInputError
from app.founder_goals.models import FounderGoal
from app.founder_goals.repository import FounderGoalRepository

MAX_TITLE_LENGTH = 200
MAX_SUBTITLE_LENGTH = 500


def _clean_title(title: str) -> str:
    title = title.strip()
    if not title:
        raise InvalidFounderGoalInputError("title", "cannot be empty")
    if len(title) > MAX_TITLE_LENGTH:
        raise InvalidFounderGoalInputError("title", f"must be {MAX_TITLE_LENGTH} characters or fewer")
    return title


def _clean_subtitle(subtitle: str | None) -> str:
    subtitle = (subtitle or "").strip()
    if len(subtitle) > MAX_SUBTITLE_LENGTH:
        raise InvalidFounderGoalInputError("subtitle", f"must be {MAX_SUBTITLE_LENGTH} characters or fewer")
    return subtitle


class FounderGoalService:
    def __init__(
        self,
        repository: FounderGoalRepository,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ):
        self.repository = repository
        self._now = clock or (lambda: datetime.now(timezone.utc))
        self._new_id = id_factory or (lambda: uuid.uuid4().hex)

    def create_goal(self, founder_id: int, *, title: str, subtitle: str = "") -> FounderGoal:
        now = self._now()
        goal = FounderGoal(
            goal_id=self._new_id(),
            founder_id=founder_id,
            title=_clean_title(title),
            subtitle=_clean_subtitle(subtitle),
            created_at=now,
            updated_at=now,
        )
        return self.repository.add(goal)

    def list_goals(self, founder_id: int) -> tuple[FounderGoal, ...]:
        return self.repository.list_for_founder(founder_id)

    def update_goal(
        self, founder_id: int, goal_id: str, *,
        title: str | None = None, subtitle: str | None = None,
    ) -> FounderGoal:
        goal = self.repository.get(goal_id)
        if goal is None or goal.founder_id != founder_id:
            raise FounderGoalNotFoundError(goal_id)

        updated = FounderGoal(
            goal_id=goal.goal_id,
            founder_id=goal.founder_id,
            title=_clean_title(title) if title is not None else goal.title,
            subtitle=_clean_subtitle(subtitle) if subtitle is not None else goal.subtitle,
            created_at=goal.created_at,
            updated_at=self._now(),
        )
        return self.repository.replace(updated)

    def delete_goal(self, founder_id: int, goal_id: str) -> None:
        goal = self.repository.get(goal_id)
        if goal is None or goal.founder_id != founder_id:
            raise FounderGoalNotFoundError(goal_id)
        self.repository.delete(goal_id)


def build_founder_goal_service(
    repository: FounderGoalRepository | None = None,
    *,
    clock: Callable[[], datetime] | None = None,
    id_factory: Callable[[], str] | None = None,
) -> FounderGoalService:
    """Factory. Defaults to the in-memory repository (tests/offline)."""
    from app.founder_goals.repository import InMemoryFounderGoalRepository

    return FounderGoalService(repository or InMemoryFounderGoalRepository(),
                              clock=clock, id_factory=id_factory)
