"""Sensible defaults for a founder's settings (Part 3)."""

from __future__ import annotations

from datetime import datetime

from app.settings.schemas import ReminderPreferences, SecurityPreferences, SettingsSnapshot

DEFAULT_REMINDER_TIME = "09:00"
DEFAULT_SESSION_TIMEOUT_MINUTES = 60


def default_reminders() -> ReminderPreferences:
    return ReminderPreferences(
        daily_reminders=True, reminder_time=DEFAULT_REMINDER_TIME,
        task_reminders=True, meeting_reminders=True, goal_reminders=True,
    )


def default_security() -> SecurityPreferences:
    return SecurityPreferences(
        session_timeout_minutes=DEFAULT_SESSION_TIMEOUT_MINUTES, login_notifications=True,
    )


def default_settings(founder_id: int, now: datetime) -> SettingsSnapshot:
    return SettingsSnapshot(
        founder_id=founder_id, reminders=default_reminders(), security=default_security(),
        created_at=now, updated_at=now,
    )
