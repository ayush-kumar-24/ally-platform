"""Fail-closed validation for the settings this module owns (Part 4).

Only the new fields are validated here (reminder_time, session_timeout_minutes).
Profile/account fields (timezone, language, phone, email) are validated in their
existing homes -- the /profile endpoints and the account schema -- and are not
duplicated (see the extend-existing decision in __init__.py).
"""

from __future__ import annotations

import re

from app.settings.errors import InvalidSettingError

_TIME_24H = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
MIN_SESSION_TIMEOUT = 5
MAX_SESSION_TIMEOUT = 1440   # 24h


def validate_reminder_time(value: str) -> None:
    if not isinstance(value, str) or not _TIME_24H.match(value):
        raise InvalidSettingError("reminder_time", "must be 'HH:MM' in 24-hour form (e.g. 09:00)")


def validate_session_timeout(value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidSettingError("session_timeout_minutes", "must be an integer")
    if not (MIN_SESSION_TIMEOUT <= value <= MAX_SESSION_TIMEOUT):
        raise InvalidSettingError(
            "session_timeout_minutes",
            f"must be between {MIN_SESSION_TIMEOUT} and {MAX_SESSION_TIMEOUT} minutes",
        )
