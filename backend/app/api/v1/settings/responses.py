"""Response models for the settings-preferences endpoints (Phase 11).

Strongly-typed Pydantic boundary models with `from_domain` mappers -- the domain
dataclasses never touch the wire."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class RemindersResponse(BaseModel):
    daily_reminders: bool
    reminder_time: str
    task_reminders: bool
    meeting_reminders: bool
    goal_reminders: bool

    @classmethod
    def from_domain(cls, r) -> "RemindersResponse":
        return cls(daily_reminders=r.daily_reminders, reminder_time=r.reminder_time,
                   task_reminders=r.task_reminders, meeting_reminders=r.meeting_reminders,
                   goal_reminders=r.goal_reminders)


class SecurityPrefsResponse(BaseModel):
    session_timeout_minutes: int
    login_notifications: bool

    @classmethod
    def from_domain(cls, s) -> "SecurityPrefsResponse":
        return cls(session_timeout_minutes=s.session_timeout_minutes,
                   login_notifications=s.login_notifications)


class SettingsPreferencesResponse(BaseModel):
    founder_id: int
    reminders: RemindersResponse
    security: SecurityPrefsResponse
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, snapshot) -> "SettingsPreferencesResponse":
        return cls(
            founder_id=snapshot.founder_id,
            reminders=RemindersResponse.from_domain(snapshot.reminders),
            security=SecurityPrefsResponse.from_domain(snapshot.security),
            created_at=snapshot.created_at, updated_at=snapshot.updated_at,
        )
