"""Achievements errors. AppError subclasses -> mapped to consistent JSON."""

from fastapi import status

from app.middleware.error_handler import AppError


class AchievementError(AppError):
    """Base for achievement failures."""


class AchievementNotFoundError(AchievementError):
    def __init__(self, achievement_id: str):
        super().__init__(f"Achievement '{achievement_id}' was not found.",
                         status_code=status.HTTP_404_NOT_FOUND)


class InvalidAchievementInputError(AchievementError):
    def __init__(self, field: str, reason: str):
        super().__init__(f"Invalid {field}: {reason}.", status_code=422)


class AchievementsLockedError(AchievementError):
    """The founder hasn't talked to Ally enough yet -- see Engagement.unlocked.
    403, not 404: the feature exists, it's just not earned yet."""

    def __init__(self):
        super().__init__(
            "Achievements unlocks once you've talked to Ally a bit more.",
            status_code=status.HTTP_403_FORBIDDEN,
        )
