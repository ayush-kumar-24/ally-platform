"""Domain DTOs for the Settings module.

Immutable frozen dataclasses -- the service returns these (never ORM rows), so the
persistence layer can be swapped (in-memory <-> SQLAlchemy) without changing the
service or the API. `SettingsSnapshot` is one founder's full settings record.

Scope note (see app/settings/__init__.py): this module owns the settings that had
no home before -- reminder preferences and app-level security preferences. Profile
lives on /profile, notifications on `founders.notification_preferences`, and
credentials/2FA are owned by the identity provider. Those are NOT duplicated here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ReminderPreferences:
    daily_reminders: bool
    reminder_time: str            # "HH:MM" 24-hour, founder-local
    task_reminders: bool
    meeting_reminders: bool
    goal_reminders: bool


@dataclass(frozen=True)
class SecurityPreferences:
    """App-level security preferences. Credentials, password and 2FA are owned by
    the identity provider (social login) and are NOT stored here."""

    session_timeout_minutes: int
    login_notifications: bool


@dataclass(frozen=True)
class SettingsSnapshot:
    founder_id: int
    reminders: ReminderPreferences
    security: SecurityPreferences
    created_at: datetime
    updated_at: datetime
