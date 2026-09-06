"""Request models for the settings-preferences endpoints (Phase 11).

Named `preferences_schemas` to avoid clashing with the existing
`app/schemas/settings.py`. All updates are partial (only sent fields change) and
`extra="forbid"` rejects unknown keys (fail closed)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


# REMOVED 2026-09-05 (team decision): the reminder preferences -- reminder_time, daily_reminders, task_reminders and goal_reminders.
# All four validated, persisted and read back through a working API, and nothing anywhere acted on any of them; none was surfaced in the UI either.
# They were the shape of a daily-digest feature that was never built.
# Removed rather than left dormant: a setting a founder cannot reach, that would do nothing if they could, is not a feature waiting to happen -- it is a thing that has to be explained every time somebody reads the schema.
# If the digest is built later, the settings come back with it.


class SecurityPrefsUpdate(BaseModel):
    """Security preferences.

    `session_timeout_minutes` was removed on 2026-09-05. It validated, persisted
    and read back, and nothing anywhere acted on it: a founder setting 5 minutes
    got the same 30-day session as everyone else, because sessions are governed
    by the access-token lifetime and the refresh cookie. A security setting that
    silently does nothing is worse than not offering one -- it is a false
    assurance, and the sort of thing that reads very badly in a security review.

    `login_notifications` stayed, and now has a consumer: see
    app/services/login_notifications.py.
    """

    model_config = ConfigDict(extra="forbid")

    login_notifications: bool | None = None
