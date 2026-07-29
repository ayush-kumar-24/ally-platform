"""Planning domain models (Phase: Founder Action Plans).

Immutable frozen dataclasses forming a Plan -> Goal -> Task hierarchy. A Plan groups
Goals; a Goal groups Tasks (the action items). Goals and Tasks are trackable
(status / priority / date). The service returns these; the persistence layer maps to
and from them, so it can be swapped (in-memory <-> SQLAlchemy) without service change.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
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


@dataclass(frozen=True)
class GoalWithTasks:
    goal: Goal
    tasks: tuple[Task, ...]


@dataclass(frozen=True)
class PlanDetail:
    """A plan with its goals and each goal's tasks -- the full plan view."""

    plan: Plan
    goals: tuple[GoalWithTasks, ...]
