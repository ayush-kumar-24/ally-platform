"""SQLAlchemy-backed PlanningRepository (production).

Maps ORM rows <-> frozen domain models. Untested in the hermetic suite (no live DB);
mirrors the app's other repositories (commit + return the domain object).
"""

from __future__ import annotations

from app.planning.db_models import GoalRow, PlanRow, ReminderRow, TaskRow
from app.planning.models import (
    Goal,
    ItemSource,
    Plan,
    PlanStatus,
    Priority,
    ProgressStatus,
    Reminder,
    ReminderChannel,
    ReminderStatus,
    Task,
)
from app.planning.repository import PlanningRepository


def _reminder(row: ReminderRow) -> Reminder:
    return Reminder(reminder_id=row.reminder_id, task_id=row.task_id, plan_id=row.plan_id,
                    founder_id=row.founder_id, remind_at=row.remind_at,
                    channel=ReminderChannel(row.channel), status=ReminderStatus(row.status),
                    note=row.note, created_at=row.created_at, updated_at=row.updated_at,
                    sent_at=row.sent_at)


def _plan(row: PlanRow) -> Plan:
    return Plan(plan_id=row.plan_id, founder_id=row.founder_id, title=row.title,
                description=row.description, status=PlanStatus(row.status),
                created_at=row.created_at, updated_at=row.updated_at)


def _goal(row: GoalRow) -> Goal:
    return Goal(goal_id=row.goal_id, plan_id=row.plan_id, founder_id=row.founder_id, title=row.title,
                description=row.description, status=ProgressStatus(row.status),
                priority=Priority(row.priority), target_date=row.target_date,
                source=ItemSource(row.source), created_at=row.created_at, updated_at=row.updated_at,
                completed_at=row.completed_at)


def _task(row: TaskRow) -> Task:
    return Task(task_id=row.task_id, goal_id=row.goal_id, plan_id=row.plan_id, founder_id=row.founder_id,
                title=row.title, status=ProgressStatus(row.status), priority=Priority(row.priority),
                due_date=row.due_date, source=ItemSource(row.source), created_at=row.created_at,
                updated_at=row.updated_at, completed_at=row.completed_at)


class SqlAlchemyPlanningRepository(PlanningRepository):
    def __init__(self, db):
        self.db = db

    # --- plans -----------------------------------------------------------
    def add_plan(self, plan):
        row = PlanRow(plan_id=plan.plan_id, founder_id=plan.founder_id, title=plan.title,
                      description=plan.description, status=plan.status.value,
                      created_at=plan.created_at, updated_at=plan.updated_at)
        self.db.add(row)
        self.db.commit()
        return plan

    def get_plan(self, plan_id):
        row = self.db.get(PlanRow, plan_id)
        return _plan(row) if row else None

    def replace_plan(self, plan):
        row = self.db.get(PlanRow, plan.plan_id)
        if row is None:
            return self.add_plan(plan)
        row.title, row.description, row.status = plan.title, plan.description, plan.status.value
        row.updated_at = plan.updated_at
        self.db.commit()
        return plan

    def list_plans(self, founder_id, *, statuses):
        rows = (self.db.query(PlanRow)
                .filter(PlanRow.founder_id == founder_id,
                        PlanRow.status.in_([s.value for s in statuses]))
                .order_by(PlanRow.created_at, PlanRow.plan_id).all())
        return tuple(_plan(r) for r in rows)

    # --- goals -----------------------------------------------------------
    def add_goal(self, goal):
        self.db.add(GoalRow(
            goal_id=goal.goal_id, plan_id=goal.plan_id, founder_id=goal.founder_id, title=goal.title,
            description=goal.description, status=goal.status.value, priority=goal.priority.value,
            target_date=goal.target_date, source=goal.source.value, created_at=goal.created_at,
            updated_at=goal.updated_at, completed_at=goal.completed_at))
        self.db.commit()
        return goal

    def get_goal(self, goal_id):
        row = self.db.get(GoalRow, goal_id)
        return _goal(row) if row else None

    def replace_goal(self, goal):
        row = self.db.get(GoalRow, goal.goal_id)
        if row is None:
            return self.add_goal(goal)
        row.title, row.description, row.status = goal.title, goal.description, goal.status.value
        row.priority, row.target_date = goal.priority.value, goal.target_date
        row.updated_at, row.completed_at = goal.updated_at, goal.completed_at
        self.db.commit()
        return goal

    def list_goals(self, plan_id):
        rows = (self.db.query(GoalRow).filter(GoalRow.plan_id == plan_id)
                .order_by(GoalRow.created_at, GoalRow.goal_id).all())
        return tuple(_goal(r) for r in rows)

    # --- tasks -----------------------------------------------------------
    def add_task(self, task):
        self.db.add(TaskRow(
            task_id=task.task_id, goal_id=task.goal_id, plan_id=task.plan_id, founder_id=task.founder_id,
            title=task.title, status=task.status.value, priority=task.priority.value,
            due_date=task.due_date, source=task.source.value, created_at=task.created_at,
            updated_at=task.updated_at, completed_at=task.completed_at))
        self.db.commit()
        return task

    def get_task(self, task_id):
        row = self.db.get(TaskRow, task_id)
        return _task(row) if row else None

    def replace_task(self, task):
        row = self.db.get(TaskRow, task.task_id)
        if row is None:
            return self.add_task(task)
        row.title, row.status, row.priority = task.title, task.status.value, task.priority.value
        row.due_date, row.updated_at, row.completed_at = task.due_date, task.updated_at, task.completed_at
        self.db.commit()
        return task

    def list_tasks(self, goal_id):
        rows = (self.db.query(TaskRow).filter(TaskRow.goal_id == goal_id)
                .order_by(TaskRow.created_at, TaskRow.task_id).all())
        return tuple(_task(r) for r in rows)

    def delete_task(self, task_id):
        row = self.db.get(TaskRow, task_id)
        if row is not None:
            self.db.delete(row)
            self.db.commit()

    # --- reminders -------------------------------------------------------
    def add_reminder(self, reminder):
        self.db.add(ReminderRow(
            reminder_id=reminder.reminder_id, task_id=reminder.task_id, plan_id=reminder.plan_id,
            founder_id=reminder.founder_id, remind_at=reminder.remind_at,
            channel=reminder.channel.value, status=reminder.status.value, note=reminder.note,
            created_at=reminder.created_at, updated_at=reminder.updated_at, sent_at=reminder.sent_at))
        self.db.commit()
        return reminder

    def get_reminder(self, reminder_id):
        row = self.db.get(ReminderRow, reminder_id)
        return _reminder(row) if row else None

    def replace_reminder(self, reminder):
        row = self.db.get(ReminderRow, reminder.reminder_id)
        if row is None:
            return self.add_reminder(reminder)
        row.status, row.note, row.remind_at = reminder.status.value, reminder.note, reminder.remind_at
        row.channel, row.updated_at, row.sent_at = reminder.channel.value, reminder.updated_at, reminder.sent_at
        self.db.commit()
        return reminder

    def list_reminders(self, founder_id, *, task_id=None):
        q = self.db.query(ReminderRow).filter(ReminderRow.founder_id == founder_id)
        if task_id is not None:
            q = q.filter(ReminderRow.task_id == task_id)
        rows = q.order_by(ReminderRow.remind_at, ReminderRow.reminder_id).all()
        return tuple(_reminder(r) for r in rows)

    def due_reminders(self, before):
        rows = (self.db.query(ReminderRow)
                .filter(ReminderRow.status == ReminderStatus.SCHEDULED.value,
                        ReminderRow.remind_at <= before)
                .order_by(ReminderRow.remind_at, ReminderRow.reminder_id).all())
        return tuple(_reminder(r) for r in rows)
