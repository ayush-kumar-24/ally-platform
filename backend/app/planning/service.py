"""PlanningService -- founder action plans (Plan -> Goal -> Task).

Repository-driven, deterministic (injected clock + id_factory). Enforces founder
ownership on every access (a foreign or missing item is reported as NotFound).
Setting a goal/task to DONE stamps completed_at; moving it off DONE clears it.
`seed_from_diagnosis` composes read-only diagnosis steps into DIAGNOSIS-sourced items
-- it never modifies Phase 5.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import date, datetime, timezone
from typing import Callable, Sequence

from app.planning.defaults import DEFAULT_PLAN_STATUS, DEFAULT_PRIORITY, DEFAULT_PROGRESS
from app.planning.errors import (
    GoalNotFoundError,
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
from app.planning.repository import PlanningRepository
from app.planning.validators import validate_description, validate_title

_ACTIVE_STATUSES = (PlanStatus.ACTIVE, PlanStatus.COMPLETED)


class PlanningService:
    def __init__(self, repository: PlanningRepository, *,
                 clock: Callable[[], datetime] | None = None,
                 id_factory: Callable[[], str] | None = None):
        self.repository = repository
        self._now = clock or (lambda: datetime.now(timezone.utc))
        self._new_id = id_factory or (lambda: uuid.uuid4().hex)

    # --- plans -----------------------------------------------------------

    def create_plan(self, founder_id: int, *, title: str, description: str = "") -> Plan:
        now = self._now()
        plan = Plan(plan_id=self._new_id(), founder_id=founder_id,
                    title=validate_title("title", title), description=validate_description(description),
                    status=DEFAULT_PLAN_STATUS, created_at=now, updated_at=now)
        return self.repository.add_plan(plan)

    def get_plan(self, founder_id: int, plan_id: str) -> Plan:
        plan = self.repository.get_plan(plan_id)
        if plan is None or plan.founder_id != founder_id:
            raise PlanNotFoundError(plan_id)
        return plan

    def list_plans(self, founder_id: int, *, include_archived: bool = False) -> tuple[Plan, ...]:
        statuses = _ACTIVE_STATUSES + ((PlanStatus.ARCHIVED,) if include_archived else ())
        return self.repository.list_plans(founder_id, statuses=statuses)

    def update_plan(self, founder_id: int, plan_id: str, *, title: str | None = None,
                    description: str | None = None, status: PlanStatus | None = None) -> Plan:
        plan = self.get_plan(founder_id, plan_id)
        updated = replace(
            plan,
            title=plan.title if title is None else validate_title("title", title),
            description=plan.description if description is None else validate_description(description),
            status=plan.status if status is None else status,
            updated_at=self._now())
        return self.repository.replace_plan(updated)

    def archive_plan(self, founder_id: int, plan_id: str) -> Plan:
        return self.update_plan(founder_id, plan_id, status=PlanStatus.ARCHIVED)

    def restore_plan(self, founder_id: int, plan_id: str) -> Plan:
        return self.update_plan(founder_id, plan_id, status=PlanStatus.ACTIVE)

    def get_plan_detail(self, founder_id: int, plan_id: str) -> PlanDetail:
        plan = self.get_plan(founder_id, plan_id)
        goals = self.repository.list_goals(plan_id)
        return PlanDetail(
            plan=plan,
            goals=tuple(GoalWithTasks(goal=g, tasks=self.repository.list_tasks(g.goal_id)) for g in goals))

    # --- goals -----------------------------------------------------------

    def add_goal(self, founder_id: int, plan_id: str, *, title: str, description: str = "",
                 priority: Priority = DEFAULT_PRIORITY, target_date: date | None = None,
                 source: ItemSource = ItemSource.MANUAL) -> Goal:
        self.get_plan(founder_id, plan_id)                 # ownership of the parent plan
        now = self._now()
        goal = Goal(goal_id=self._new_id(), plan_id=plan_id, founder_id=founder_id,
                    title=validate_title("title", title), description=validate_description(description),
                    status=DEFAULT_PROGRESS, priority=priority, target_date=target_date,
                    source=source, created_at=now, updated_at=now)
        return self.repository.add_goal(goal)

    def get_goal(self, founder_id: int, goal_id: str) -> Goal:
        goal = self.repository.get_goal(goal_id)
        if goal is None or goal.founder_id != founder_id:
            raise GoalNotFoundError(goal_id)
        return goal

    def list_goals(self, founder_id: int, plan_id: str) -> tuple[Goal, ...]:
        self.get_plan(founder_id, plan_id)
        return self.repository.list_goals(plan_id)

    def update_goal(self, founder_id: int, goal_id: str, *, title: str | None = None,
                    description: str | None = None, status: ProgressStatus | None = None,
                    priority: Priority | None = None, target_date: date | None = None,
                    clear_target_date: bool = False) -> Goal:
        goal = self.get_goal(founder_id, goal_id)
        now = self._now()
        new_status = goal.status if status is None else status
        updated = replace(
            goal,
            title=goal.title if title is None else validate_title("title", title),
            description=goal.description if description is None else validate_description(description),
            status=new_status, priority=goal.priority if priority is None else priority,
            target_date=None if clear_target_date else (goal.target_date if target_date is None else target_date),
            completed_at=self._completion(goal.completed_at, new_status, now), updated_at=now)
        return self.repository.replace_goal(updated)

    # --- tasks -----------------------------------------------------------

    def add_task(self, founder_id: int, goal_id: str, *, title: str,
                 priority: Priority = DEFAULT_PRIORITY, due_date: date | None = None,
                 source: ItemSource = ItemSource.MANUAL) -> Task:
        goal = self.get_goal(founder_id, goal_id)
        now = self._now()
        task = Task(task_id=self._new_id(), goal_id=goal_id, plan_id=goal.plan_id, founder_id=founder_id,
                    title=validate_title("title", title), status=DEFAULT_PROGRESS, priority=priority,
                    due_date=due_date, source=source, created_at=now, updated_at=now)
        return self.repository.add_task(task)

    def get_task(self, founder_id: int, task_id: str) -> Task:
        task = self.repository.get_task(task_id)
        if task is None or task.founder_id != founder_id:
            raise TaskNotFoundError(task_id)
        return task

    def list_tasks(self, founder_id: int, goal_id: str) -> tuple[Task, ...]:
        self.get_goal(founder_id, goal_id)
        return self.repository.list_tasks(goal_id)

    def update_task(self, founder_id: int, task_id: str, *, title: str | None = None,
                    status: ProgressStatus | None = None, priority: Priority | None = None,
                    due_date: date | None = None, clear_due_date: bool = False) -> Task:
        task = self.get_task(founder_id, task_id)
        now = self._now()
        new_status = task.status if status is None else status
        updated = replace(
            task,
            title=task.title if title is None else validate_title("title", title),
            status=new_status, priority=task.priority if priority is None else priority,
            due_date=None if clear_due_date else (task.due_date if due_date is None else due_date),
            completed_at=self._completion(task.completed_at, new_status, now), updated_at=now)
        return self.repository.replace_task(updated)

    # --- diagnosis seeding (compose, read-only) --------------------------

    def seed_from_diagnosis(self, founder_id: int, plan_id: str, steps: Sequence[str]) -> GoalWithTasks:
        """Create a 'Diagnosis next steps' goal under the plan with one task per step.
        Steps come from the frozen diagnosis (next_steps / priority_actions); this
        service only reads the provided strings and never touches Phase 5."""
        cleaned = [s.strip() for s in steps if s and s.strip()]
        goal = self.add_goal(founder_id, plan_id, title="Diagnosis next steps",
                             source=ItemSource.DIAGNOSIS)
        tasks = tuple(self.add_task(founder_id, goal.goal_id, title=step, source=ItemSource.DIAGNOSIS)
                      for step in cleaned)
        return GoalWithTasks(goal=goal, tasks=tasks)

    # --- internals -------------------------------------------------------

    @staticmethod
    def _completion(current: datetime | None, status: ProgressStatus, now: datetime) -> datetime | None:
        if status == ProgressStatus.DONE:
            return current or now                          # stamp once, keep the original
        return None                                        # cleared when moved off DONE


def build_planning_service(repository: PlanningRepository | None = None, *,
                           clock=None, id_factory=None) -> PlanningService:
    from app.planning.repository import InMemoryPlanningRepository
    return PlanningService(repository or InMemoryPlanningRepository(), clock=clock, id_factory=id_factory)
