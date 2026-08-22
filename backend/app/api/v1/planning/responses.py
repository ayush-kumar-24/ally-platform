"""Planning API response models with `from_domain` mappers."""

from __future__ import annotations

from datetime import date, datetime, time

from pydantic import BaseModel


class PlanResponse(BaseModel):
    plan_id: str
    founder_id: int
    title: str
    description: str
    status: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, p) -> "PlanResponse":
        return cls(plan_id=p.plan_id, founder_id=p.founder_id, title=p.title,
                   description=p.description, status=p.status.value,
                   created_at=p.created_at, updated_at=p.updated_at)


class GoalResponse(BaseModel):
    goal_id: str
    plan_id: str
    founder_id: int
    title: str
    description: str
    status: str
    priority: str
    target_date: date | None
    source: str
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None

    @classmethod
    def from_domain(cls, g) -> "GoalResponse":
        return cls(goal_id=g.goal_id, plan_id=g.plan_id, founder_id=g.founder_id, title=g.title,
                   description=g.description, status=g.status.value, priority=g.priority.value,
                   target_date=g.target_date, source=g.source.value, created_at=g.created_at,
                   updated_at=g.updated_at, completed_at=g.completed_at)


class TaskResponse(BaseModel):
    task_id: str
    goal_id: str
    plan_id: str
    founder_id: int
    title: str
    status: str
    priority: str
    due_date: date | None
    source: str
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    due_time: time | None = None
    # synced | failed | skipped | pending. The UI badges this so a founder is
    # never left believing something reached their calendar when it did not.
    calendar_sync_status: str = "skipped"

    @classmethod
    def from_domain(cls, t) -> "TaskResponse":
        return cls(task_id=t.task_id, goal_id=t.goal_id, plan_id=t.plan_id, founder_id=t.founder_id,
                   title=t.title, status=t.status.value, priority=t.priority.value, due_date=t.due_date,
                   source=t.source.value, created_at=t.created_at, updated_at=t.updated_at,
                   completed_at=t.completed_at, due_time=t.due_time,
                   calendar_sync_status=t.calendar_sync_status)


class GoalWithTasksResponse(BaseModel):
    goal: GoalResponse
    tasks: list[TaskResponse]

    @classmethod
    def from_domain(cls, gwt) -> "GoalWithTasksResponse":
        return cls(goal=GoalResponse.from_domain(gwt.goal),
                   tasks=[TaskResponse.from_domain(t) for t in gwt.tasks])


class PlanDetailResponse(BaseModel):
    plan: PlanResponse
    goals: list[GoalWithTasksResponse]

    @classmethod
    def from_domain(cls, detail) -> "PlanDetailResponse":
        return cls(plan=PlanResponse.from_domain(detail.plan),
                   goals=[GoalWithTasksResponse.from_domain(g) for g in detail.goals])


class ProgressCountsResponse(BaseModel):
    total: int
    todo: int
    in_progress: int
    done: int
    percent_complete: int

    @classmethod
    def from_domain(cls, c) -> "ProgressCountsResponse":
        return cls(total=c.total, todo=c.todo, in_progress=c.in_progress,
                   done=c.done, percent_complete=c.percent_complete)


class GoalProgressResponse(BaseModel):
    goal_id: str
    title: str
    status: str
    tasks: ProgressCountsResponse

    @classmethod
    def from_domain(cls, g) -> "GoalProgressResponse":
        return cls(goal_id=g.goal_id, title=g.title, status=g.status.value,
                   tasks=ProgressCountsResponse.from_domain(g.tasks))


class PlanProgressResponse(BaseModel):
    plan_id: str
    tasks: ProgressCountsResponse            # across every task in the plan
    goals: ProgressCountsResponse            # the goals, counted by status
    per_goal: list[GoalProgressResponse]

    @classmethod
    def from_domain(cls, p) -> "PlanProgressResponse":
        return cls(plan_id=p.plan_id,
                   tasks=ProgressCountsResponse.from_domain(p.tasks),
                   goals=ProgressCountsResponse.from_domain(p.goals),
                   per_goal=[GoalProgressResponse.from_domain(g) for g in p.per_goal])


class PlanListResponse(BaseModel):
    plans: list[PlanResponse]
    total: int


class GoalListResponse(BaseModel):
    goals: list[GoalResponse]
    total: int


class TaskListResponse(BaseModel):
    tasks: list[TaskResponse]
    total: int


class ReminderResponse(BaseModel):
    reminder_id: str
    task_id: str
    plan_id: str
    remind_at: datetime
    channel: str
    status: str
    note: str
    sent_at: datetime | None = None

    @classmethod
    def from_domain(cls, r) -> "ReminderResponse":
        return cls(reminder_id=r.reminder_id, task_id=r.task_id, plan_id=r.plan_id,
                   remind_at=r.remind_at, channel=r.channel.value, status=r.status.value,
                   note=r.note, sent_at=r.sent_at)


class ReminderListResponse(BaseModel):
    reminders: list[ReminderResponse]
    total: int
