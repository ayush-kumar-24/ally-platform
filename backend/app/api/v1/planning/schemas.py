"""Planning API request models (Pydantic v2). Domain enums are reused directly."""

from __future__ import annotations

from datetime import date, datetime

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


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, max_length=200)
    status: ProgressStatus | None = None
    priority: Priority | None = None
    due_date: date | None = None
