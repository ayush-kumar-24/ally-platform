"""Planning persistence seam.

`PlanningRepository` covers all three levels (plans / goals / tasks). Two
implementations: InMemory (deterministic, thread-safe, tests) and SQLAlchemy
(production). Swapping is a repository replacement only; the service is unchanged.
"""

from __future__ import annotations

import abc
import threading

from app.planning.models import Goal, Plan, PlanStatus, Reminder, ReminderStatus, Task


class PlanningRepository(abc.ABC):
    # --- plans -----------------------------------------------------------
    @abc.abstractmethod
    def add_plan(self, plan: Plan) -> Plan: ...

    @abc.abstractmethod
    def get_plan(self, plan_id: str) -> Plan | None: ...

    @abc.abstractmethod
    def replace_plan(self, plan: Plan) -> Plan: ...

    @abc.abstractmethod
    def list_plans(self, founder_id: int, *, statuses: tuple[PlanStatus, ...]) -> tuple[Plan, ...]: ...

    # --- goals -----------------------------------------------------------
    @abc.abstractmethod
    def add_goal(self, goal: Goal) -> Goal: ...

    @abc.abstractmethod
    def get_goal(self, goal_id: str) -> Goal | None: ...

    @abc.abstractmethod
    def replace_goal(self, goal: Goal) -> Goal: ...

    @abc.abstractmethod
    def list_goals(self, plan_id: str) -> tuple[Goal, ...]: ...

    # --- tasks -----------------------------------------------------------
    @abc.abstractmethod
    def add_task(self, task: Task) -> Task: ...

    @abc.abstractmethod
    def get_task(self, task_id: str) -> Task | None: ...

    @abc.abstractmethod
    def replace_task(self, task: Task) -> Task: ...

    @abc.abstractmethod
    def list_tasks(self, goal_id: str) -> tuple[Task, ...]: ...

    @abc.abstractmethod
    def delete_task(self, task_id: str) -> None: ...

    # reminders
    @abc.abstractmethod
    def add_reminder(self, reminder: "Reminder") -> "Reminder": ...

    @abc.abstractmethod
    def get_reminder(self, reminder_id: str) -> "Reminder | None": ...

    @abc.abstractmethod
    def replace_reminder(self, reminder: "Reminder") -> "Reminder": ...

    @abc.abstractmethod
    def list_reminders(self, founder_id: int, *, task_id: str | None = None) -> "tuple[Reminder, ...]": ...

    @abc.abstractmethod
    def due_reminders(self, before) -> "tuple[Reminder, ...]": ...


class InMemoryPlanningRepository(PlanningRepository):
    def __init__(self) -> None:
        self._plans: dict[str, Plan] = {}
        self._goals: dict[str, Goal] = {}
        self._tasks: dict[str, Task] = {}
        self._reminders: dict[str, Reminder] = {}
        self._lock = threading.RLock()

    # plans
    def add_plan(self, plan):
        with self._lock:
            self._plans[plan.plan_id] = plan
        return plan

    def get_plan(self, plan_id):
        with self._lock:
            return self._plans.get(plan_id)

    def replace_plan(self, plan):
        with self._lock:
            self._plans[plan.plan_id] = plan
        return plan

    def list_plans(self, founder_id, *, statuses):
        with self._lock:
            items = [p for p in self._plans.values()
                     if p.founder_id == founder_id and p.status in statuses]
        items.sort(key=lambda p: (p.created_at, p.plan_id))
        return tuple(items)

    # goals
    def add_goal(self, goal):
        with self._lock:
            self._goals[goal.goal_id] = goal
        return goal

    def get_goal(self, goal_id):
        with self._lock:
            return self._goals.get(goal_id)

    def replace_goal(self, goal):
        with self._lock:
            self._goals[goal.goal_id] = goal
        return goal

    def list_goals(self, plan_id):
        with self._lock:
            items = [g for g in self._goals.values() if g.plan_id == plan_id]
        items.sort(key=lambda g: (g.created_at, g.goal_id))
        return tuple(items)

    # tasks
    def add_task(self, task):
        with self._lock:
            self._tasks[task.task_id] = task
        return task

    def get_task(self, task_id):
        with self._lock:
            return self._tasks.get(task_id)

    def replace_task(self, task):
        with self._lock:
            self._tasks[task.task_id] = task
        return task

    def list_tasks(self, goal_id):
        with self._lock:
            items = [t for t in self._tasks.values() if t.goal_id == goal_id]
        items.sort(key=lambda t: (t.created_at, t.task_id))
        return tuple(items)

    def delete_task(self, task_id):
        with self._lock:
            self._tasks.pop(task_id, None)

    # reminders
    def add_reminder(self, reminder):
        with self._lock:
            self._reminders[reminder.reminder_id] = reminder
        return reminder

    def get_reminder(self, reminder_id):
        with self._lock:
            return self._reminders.get(reminder_id)

    def replace_reminder(self, reminder):
        with self._lock:
            self._reminders[reminder.reminder_id] = reminder
        return reminder

    def list_reminders(self, founder_id, *, task_id=None):
        with self._lock:
            items = [r for r in self._reminders.values()
                     if r.founder_id == founder_id and (task_id is None or r.task_id == task_id)]
        items.sort(key=lambda r: (r.remind_at, r.reminder_id))
        return tuple(items)

    def due_reminders(self, before):
        with self._lock:
            items = [r for r in self._reminders.values()
                     if r.status == ReminderStatus.SCHEDULED and r.remind_at <= before]
        items.sort(key=lambda r: (r.remind_at, r.reminder_id))
        return tuple(items)
