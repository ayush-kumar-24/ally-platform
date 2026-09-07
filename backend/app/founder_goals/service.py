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
        achievements=None,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ):
        self.repository = repository
        # Optional collaborator, injected rather than imported, so this service
        # keeps its own tests hermetic and a deployment without achievements
        # still completes goals. Same shape as PaymentService's credits/coupons.
        self.achievements = achievements
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

    def set_completed(self, founder_id: int, goal_id: str, completed: bool) -> FounderGoal:
        """Mark a goal reached, or reopen one.

        Completing writes an achievement, because a goal the founder has
        actually hit is the clearest example of the thing that page is for --
        and until now every entry there had to be typed a second time by hand.

        Only the TRANSITION writes one. Completing an already-completed goal is
        a no-op rather than a second trophy, which is what makes this safe to
        call from anywhere -- a double-tap, a retried request, or (later) Ally
        acting on something the founder said twice.

        Reopening clears `completed_at` but deliberately leaves the achievement
        standing: it records that this was reached on that date, which stays
        true even if the founder raises the bar afterwards. Deleting it is
        theirs to do, on the page that owns it.
        """
        goal = self.repository.get(goal_id)
        if goal is None or goal.founder_id != founder_id:
            raise FounderGoalNotFoundError(goal_id)

        now = self._now()
        if completed == goal.is_completed:
            return goal

        updated = FounderGoal(
            goal_id=goal.goal_id,
            founder_id=goal.founder_id,
            title=goal.title,
            subtitle=goal.subtitle,
            created_at=goal.created_at,
            updated_at=now,
            completed_at=now if completed else None,
        )
        saved = self.repository.replace(updated)

        if completed and self.achievements is not None:
            try:
                self.achievements.create_achievement(
                    founder_id,
                    title=goal.title,
                    description=goal.subtitle,
                    category="Goal reached",
                    occurred_on=now.strftime("%b %Y"),
                    # Earned, not authored: this founder hit the goal, so the
                    # engagement gate on hand-written entries does not apply.
                    earned=True,
                )
            except Exception:  # noqa: BLE001
                # The goal IS complete -- that is the founder's own record of
                # their work and it is already saved. Failing the request now
                # would tell them otherwise over a bookkeeping problem on a
                # page they were not even looking at.
                from app.core.logger import logger
                logger.error("goals: completed but could not write the achievement",
                             extra={"founder_id": founder_id, "goal_id": goal_id})
        return saved

    def delete_goal(self, founder_id: int, goal_id: str) -> None:
        goal = self.repository.get(goal_id)
        if goal is None or goal.founder_id != founder_id:
            raise FounderGoalNotFoundError(goal_id)
        self.repository.delete(goal_id)


def build_founder_goal_service(
    repository: FounderGoalRepository | None = None,
    *,
    achievements=None,
    clock: Callable[[], datetime] | None = None,
    id_factory: Callable[[], str] | None = None,
) -> FounderGoalService:
    """Factory. Defaults to the in-memory repository (tests/offline)."""
    from app.founder_goals.repository import InMemoryFounderGoalRepository

    return FounderGoalService(repository or InMemoryFounderGoalRepository(),
                              achievements=achievements,
                              clock=clock, id_factory=id_factory)
