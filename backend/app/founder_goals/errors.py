"""Founder Goals errors. AppError subclasses -> mapped to consistent JSON."""

from fastapi import status

from app.middleware.error_handler import AppError


class FounderGoalError(AppError):
    """Base for founder-goal failures."""


class FounderGoalNotFoundError(FounderGoalError):
    def __init__(self, goal_id: str):
        super().__init__(f"Goal '{goal_id}' was not found.", status_code=status.HTTP_404_NOT_FOUND)


class InvalidFounderGoalInputError(FounderGoalError):
    def __init__(self, field: str, reason: str):
        super().__init__(f"Invalid {field}: {reason}.", status_code=422)
