"""Fail-closed validation for planning inputs."""

from __future__ import annotations

from app.planning.errors import InvalidPlanningInputError

_MAX_TITLE = 200
_MAX_DESCRIPTION = 2000


def validate_title(field: str, value: str) -> str:
    text = (value or "").strip()
    if not text:
        raise InvalidPlanningInputError(field, "must not be empty")
    if len(text) > _MAX_TITLE:
        raise InvalidPlanningInputError(field, f"must be at most {_MAX_TITLE} characters")
    return text


def validate_description(value: str | None) -> str:
    text = (value or "").strip()
    if len(text) > _MAX_DESCRIPTION:
        raise InvalidPlanningInputError("description", f"must be at most {_MAX_DESCRIPTION} characters")
    return text


# A reminder lead is bounded so a typo cannot schedule a nudge in the next
# century, and floored at 0 because "remind me after it was due" is not a
# reminder. A week is the top end: anything longer is a calendar entry of its
# own, not a heads-up about this task.
_MAX_REMINDER_LEAD_MINUTES = 7 * 24 * 60


def validate_reminder_lead(value: int | None) -> int | None:
    """Minutes-before for a task reminder. None passes through untouched --
    it means "use the platform default", which is a real choice and not a
    missing value."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidPlanningInputError("reminder_minutes_before", "must be a whole number of minutes")
    if value < 0:
        raise InvalidPlanningInputError("reminder_minutes_before", "must not be negative")
    if value > _MAX_REMINDER_LEAD_MINUTES:
        raise InvalidPlanningInputError(
            "reminder_minutes_before",
            f"must be at most {_MAX_REMINDER_LEAD_MINUTES} minutes (7 days)")
    return value
