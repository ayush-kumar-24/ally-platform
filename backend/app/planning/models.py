"""Planning domain models (Phase: Founder Action Plans).

Immutable frozen dataclasses forming a Plan -> Goal -> Task hierarchy. A Plan groups
Goals; a Goal groups Tasks (the action items). Goals and Tasks are trackable
(status / priority / date). The service returns these; the persistence layer maps to
and from them, so it can be swapped (in-memory <-> SQLAlchemy) without service change.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from enum import Enum


class PlanStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ProgressStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ItemSource(str, Enum):
    MANUAL = "manual"
    DIAGNOSIS = "diagnosis"     # seeded read-only from the frozen diagnosis


@dataclass(frozen=True)
class Plan:
    plan_id: str
    founder_id: int
    title: str
    description: str
    status: PlanStatus
    created_at: datetime
    updated_at: datetime

    @property
    def is_active(self) -> bool:
        return self.status == PlanStatus.ACTIVE

    @property
    def is_archived(self) -> bool:
        return self.status == PlanStatus.ARCHIVED


@dataclass(frozen=True)
class Goal:
    goal_id: str
    plan_id: str
    founder_id: int
    title: str
    description: str
    status: ProgressStatus
    priority: Priority
    target_date: date | None
    source: ItemSource
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


@dataclass(frozen=True)
class Task:
    task_id: str
    goal_id: str
    plan_id: str
    founder_id: int
    title: str
    status: ProgressStatus
    priority: Priority
    due_date: date | None
    source: ItemSource
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    # Optional time of day. Google counts reminder offsets backwards from the
    # event start, so an all-day event (starting at midnight) cannot carry a
    # useful "30 minutes before" popup -- it would fire at 23:30 the night
    # before. A task with a time becomes a timed event; one without is placed at
    # a configured default hour. See app/calendar_sync/sync.py.
    due_time: time | None = None
    # The Google event this task owns, or None if it has never synced. Keeping
    # it is what makes an edit update the same event instead of leaving a
    # duplicate behind on every save.
    calendar_event_id: str | None = None
    # synced | failed | skipped | pending -- shown to the founder, because a
    # task they believe reached their calendar and did not is worse than one
    # they know did not.
    calendar_sync_status: str = "skipped"


@dataclass(frozen=True)
class GoalWithTasks:
    goal: Goal
    tasks: tuple[Task, ...]


@dataclass(frozen=True)
class PlanDetail:
    """A plan with its goals and each goal's tasks -- the full plan view."""

    plan: Plan
    goals: tuple[GoalWithTasks, ...]


# --- progress (derived, deterministic -- no stored field) -------------------
@dataclass(frozen=True)
class ProgressCounts:
    total: int
    todo: int
    in_progress: int
    done: int
    percent_complete: int          # round(done / total * 100); 0 when total == 0


@dataclass(frozen=True)
class GoalProgress:
    goal_id: str
    title: str
    status: ProgressStatus
    tasks: ProgressCounts


@dataclass(frozen=True)
class PlanProgress:
    """A plan's completion, computed from task/goal status -- never stored."""

    plan_id: str
    tasks: ProgressCounts          # across every task in the plan
    goals: ProgressCounts          # the goals themselves, counted by status
    per_goal: tuple[GoalProgress, ...]


# --- reminders --------------------------------------------------------------
class ReminderChannel(str, Enum):
    IN_APP = "in_app"
    EMAIL = "email"


class ReminderStatus(str, Enum):
    SCHEDULED = "scheduled"
    SENT = "sent"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class Reminder:
    """A scheduled nudge for a task. Storage + API only -- the actual delivery is a
    separate worker's job (query due_reminders, send, mark_reminder_sent)."""

    reminder_id: str
    task_id: str
    plan_id: str
    founder_id: int
    remind_at: datetime
    channel: ReminderChannel
    status: ReminderStatus
    note: str
    created_at: datetime
    updated_at: datetime
    sent_at: datetime | None = None
