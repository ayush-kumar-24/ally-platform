"""Achievements API response models with `from_domain` mappers."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AchievementResponse(BaseModel):
    achievement_id: str
    founder_id: int
    title: str
    description: str
    category: str
    occurred_on: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, a) -> "AchievementResponse":
        return cls(achievement_id=a.achievement_id, founder_id=a.founder_id, title=a.title,
                   description=a.description, category=a.category, occurred_on=a.occurred_on,
                   created_at=a.created_at, updated_at=a.updated_at)


class AchievementListResponse(BaseModel):
    achievements: list[AchievementResponse]
    total: int


class EngagementResponse(BaseModel):
    message_count: int
    threshold: int
    unlocked: bool

    @classmethod
    def from_domain(cls, e) -> "EngagementResponse":
        return cls(message_count=e.message_count, threshold=e.threshold, unlocked=e.unlocked)
