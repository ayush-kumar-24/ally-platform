"""Founder Goals API response models with `from_domain` mappers."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class FounderGoalResponse(BaseModel):
    goal_id: str
    founder_id: int
    title: str
    subtitle: str
    created_at: datetime
    updated_at: datetime
    #: null while the goal is still open. The date is sent, not just a flag,
    #: because the page shows when it was reached.
    completed_at: datetime | None = None

    @classmethod
    def from_domain(cls, g) -> "FounderGoalResponse":
        return cls(goal_id=g.goal_id, founder_id=g.founder_id, title=g.title,
                   subtitle=g.subtitle, created_at=g.created_at, updated_at=g.updated_at,
                   completed_at=g.completed_at)


class FounderGoalListResponse(BaseModel):
    goals: list[FounderGoalResponse]
    total: int
