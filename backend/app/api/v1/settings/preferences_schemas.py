"""Request models for the settings-preferences endpoints (Phase 11).

Named `preferences_schemas` to avoid clashing with the existing
`app/schemas/settings.py`. All updates are partial (only sent fields change) and
`extra="forbid"` rejects unknown keys (fail closed)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RemindersUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    daily_reminders: bool | None = None
    reminder_time: str | None = Field(default=None, max_length=5)
    task_reminders: bool | None = None
    meeting_reminders: bool | None = None
    goal_reminders: bool | None = None


class SecurityPrefsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_timeout_minutes: int | None = Field(default=None, ge=5, le=1440)
    login_notifications: bool | None = None
