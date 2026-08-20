"""Achievements -- founder-authored milestones, gated behind real Ally engagement.

Public surface (import from here, not from submodules):

    Achievement                frozen domain DTO -- one achievement
    Engagement                 message_count/threshold/unlocked -- the real gate
    AchievementService         business rules; build_achievement_service() to construct
    AchievementRepository      persistence seam (InMemory / SqlAlchemy)
    errors                     AchievementError and friends -> precise HTTP statuses

Nothing here is auto-detected -- every achievement is written by the
founder themselves (see models.py's docstring). The one thing that IS
computed rather than typed in: whether the page is unlocked at all, from
the founder's real total message count across their conversations with
Ally (service.py's UNLOCK_MESSAGE_THRESHOLD).
"""

from app.achievements.errors import (
    AchievementError,
    AchievementNotFoundError,
    AchievementsLockedError,
    InvalidAchievementInputError,
)
from app.achievements.models import Achievement, Engagement
from app.achievements.repository import AchievementRepository, InMemoryAchievementRepository
from app.achievements.service import AchievementService, build_achievement_service

__all__ = [
    "Achievement",
    "AchievementError",
    "AchievementNotFoundError",
    "AchievementRepository",
    "AchievementService",
    "AchievementsLockedError",
    "Engagement",
    "InMemoryAchievementRepository",
    "InvalidAchievementInputError",
    "build_achievement_service",
]
