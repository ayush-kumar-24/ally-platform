"""Planning module -- Founder Action Plans (Plan -> Goal -> Task).

Database-backed, repository-driven, deterministic. Founders build execution plans
(goals + action tasks with status / priority / dates) and can seed items read-only
from their frozen diagnosis's next steps. Composes existing data; modifies no
existing module. Testable fully offline (in-memory repo); production uses the
SQLAlchemy repo + planning_plans/goals/tasks tables.
"""

from app.planning.errors import (
    GoalNotFoundError,
    InvalidPlanningInputError,
    InvalidPlanStateError,
    PlanningError,
    PlanNotFoundError,
    TaskNotFoundError,
)
from app.planning.models import (
    Goal,
    GoalWithTasks,
    ItemSource,
    Plan,
    PlanDetail,
    PlanStatus,
    Priority,
    ProgressStatus,
    Task,
)
from app.planning.repository import InMemoryPlanningRepository, PlanningRepository
from app.planning.service import PlanningService, build_planning_service

__all__ = [
    # models
    "Plan", "Goal", "Task", "PlanDetail", "GoalWithTasks",
    "PlanStatus", "ProgressStatus", "Priority", "ItemSource",
    # repository / service
    "PlanningRepository", "InMemoryPlanningRepository",
    "PlanningService", "build_planning_service",
    # errors
    "PlanningError", "PlanNotFoundError", "GoalNotFoundError", "TaskNotFoundError",
    "InvalidPlanningInputError", "InvalidPlanStateError",
]
