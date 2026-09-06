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


# REMOVED 2026-09-05 (team decision): the reminder preferences -- reminder_time, daily_reminders, task_reminders and goal_reminders.
# All four validated, persisted and read back through a working API, and nothing anywhere acted on any of them; none was surfaced in the UI either.
# They were the shape of a daily-digest feature that was never built.
# Removed rather than left dormant: a setting a founder cannot reach, that would do nothing if they could, is not a feature waiting to happen -- it is a thing that has to be explained every time somebody reads the schema.
# If the digest is built later, the settings come back with it.


@dataclass(frozen=True)
class SecurityPreferences:
    """App-level security preferences. Credentials and 2FA are owned by the
    identity provider and are NOT stored here.

    `session_timeout_minutes` removed 2026-09-05 -- it had no consumer and no
    effect. See SecurityPrefsUpdate for the reasoning.
    """

    login_notifications: bool


@dataclass(frozen=True)
class SettingsSnapshot:
    founder_id: int
    security: SecurityPreferences
    created_at: datetime
    updated_at: datetime
