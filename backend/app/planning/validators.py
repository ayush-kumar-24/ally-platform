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
