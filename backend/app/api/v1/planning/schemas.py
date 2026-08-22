"""Planning API request models (Pydantic v2). Domain enums are reused directly."""

from __future__ import annotations

from datetime import date, time, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.planning.models import PlanStatus, Priority, ProgressStatus, ReminderChannel


class ReminderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    remind_at: datetime
    channel: ReminderChannel = ReminderChannel.IN_APP
    note: str = Field(default="", max_length=500)


class PlanCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)


class PlanUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    status: PlanStatus | None = None


class GoalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    priority: Priority = Priority.MEDIUM
    target_date: date | None = None


class GoalUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    status: ProgressStatus | None = None
    priority: Priority | None = None
    target_date: date | None = None


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    priority: Priority = Priority.MEDIUM
    due_date: date | None = None
    # Optional. Without a time the calendar event is placed at a configured
    # default hour, because a reminder offset is only meaningful against a
    # timed event -- see app/calendar_sync/sync.py.
    due_time: time | None = None
    # The founder's IANA zone, so "9am" means 9am where they are. Sent by the
    # browser (Intl.DateTimeFormat().resolvedOptions().timeZone). UTC is a
    # deliberate fallback rather than a guess at their location: wrong by a
    # known amount beats wrong by an unknowable one.
    timezone: str = Field(default="UTC", max_length=64)


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, max_length=200)
    status: ProgressStatus | None = None
    priority: Priority | None = None
    due_date: date | None = None
    due_time: time | None = None
    timezone: str = Field(default="UTC", max_length=64)
