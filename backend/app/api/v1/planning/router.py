"""Planning API router -- transport only. Every endpoint resolves the authenticated
founder and delegates to PlanningService; ownership + validation live in the service.
Domain errors propagate to the global handler."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.v1.planning.dependencies import (
    get_current_founder_id,
    get_diagnosis_steps,
    get_planning_service,
    require_plan_your_day,
)
from app.api.v1.planning.responses import (
    GoalListResponse,
    GoalResponse,
    GoalWithTasksResponse,
    PlanDetailResponse,
    PlanListResponse,
    PlanProgressResponse,
    PlanResponse,
    ReminderListResponse,
    ReminderResponse,
    TaskListResponse,
    TaskResponse,
)
from app.api.v1.planning.schemas import (
    GoalCreate,
    GoalUpdate,
    PlanCreate,
    PlanUpdate,
    ReminderCreate,
    TaskCreate,
    TaskUpdate,
)
from sqlalchemy.orm import Session

from app.calendar_sync import hooks
from app.db.session import get_db
from app.planning.service import PlanningService

router = APIRouter(
    prefix="/planning",
    tags=["planning"],
    # Plan-gated as a whole: every route below requires Starter or above.
    dependencies=[Depends(require_plan_your_day)],
)


def _date_kwargs(payload, field: str, clear_flag: str) -> dict:
    """Translate an optional date field into set/clear kwargs (explicit null clears)."""
    if field not in payload.model_fields_set:
        return {}
    value = getattr(payload, field)
    return {clear_flag: True} if value is None else {field: value}


# --- plans ------------------------------------------------------------------


@router.post("/plans", response_model=PlanResponse, status_code=201, summary="Create a plan")
def create_plan(payload: PlanCreate, founder_id: int = Depends(get_current_founder_id),
                service: PlanningService = Depends(get_planning_service)) -> PlanResponse:
    return PlanResponse.from_domain(
        service.create_plan(founder_id, title=payload.title, description=payload.description))


@router.get("/plans", response_model=PlanListResponse, summary="List plans")
def list_plans(include_archived: bool = False, founder_id: int = Depends(get_current_founder_id),
               service: PlanningService = Depends(get_planning_service)) -> PlanListResponse:
    items = service.list_plans(founder_id, include_archived=include_archived)
    return PlanListResponse(plans=[PlanResponse.from_domain(p) for p in items], total=len(items))


@router.get("/plans/{plan_id}", response_model=PlanDetailResponse, summary="Plan detail (with goals + tasks)")
def get_plan(plan_id: str, founder_id: int = Depends(get_current_founder_id),
             service: PlanningService = Depends(get_planning_service)) -> PlanDetailResponse:
    return PlanDetailResponse.from_domain(service.get_plan_detail(founder_id, plan_id))


@router.get("/plans/{plan_id}/progress", response_model=PlanProgressResponse,
            summary="Plan progress (task/goal completion, derived)")
def plan_progress(plan_id: str, founder_id: int = Depends(get_current_founder_id),
                  service: PlanningService = Depends(get_planning_service)) -> PlanProgressResponse:
    return PlanProgressResponse.from_domain(service.plan_progress(founder_id, plan_id))


@router.patch("/plans/{plan_id}", response_model=PlanResponse, summary="Update a plan")
def update_plan(plan_id: str, payload: PlanUpdate, founder_id: int = Depends(get_current_founder_id),
                service: PlanningService = Depends(get_planning_service)) -> PlanResponse:
    return PlanResponse.from_domain(
        service.update_plan(founder_id, plan_id, **payload.model_dump(exclude_unset=True)))


@router.delete("/plans/{plan_id}", response_model=PlanResponse, summary="Archive a plan")
def archive_plan(plan_id: str, founder_id: int = Depends(get_current_founder_id),
                 service: PlanningService = Depends(get_planning_service)) -> PlanResponse:
    return PlanResponse.from_domain(service.archive_plan(founder_id, plan_id))


@router.post("/plans/{plan_id}/restore", response_model=PlanResponse, summary="Restore a plan")
def restore_plan(plan_id: str, founder_id: int = Depends(get_current_founder_id),
                 service: PlanningService = Depends(get_planning_service)) -> PlanResponse:
    return PlanResponse.from_domain(service.restore_plan(founder_id, plan_id))


@router.post("/plans/{plan_id}/seed-from-diagnosis", response_model=GoalWithTasksResponse,
             status_code=201, summary="Seed a goal + tasks from the founder's diagnosis")
def seed_from_diagnosis(plan_id: str, founder_id: int = Depends(get_current_founder_id),
                        steps: list[str] = Depends(get_diagnosis_steps),
                        service: PlanningService = Depends(get_planning_service)) -> GoalWithTasksResponse:
    return GoalWithTasksResponse.from_domain(service.seed_from_diagnosis(founder_id, plan_id, steps))


# --- goals ------------------------------------------------------------------


@router.post("/plans/{plan_id}/goals", response_model=GoalResponse, status_code=201, summary="Add a goal")
def add_goal(plan_id: str, payload: GoalCreate, founder_id: int = Depends(get_current_founder_id),
             service: PlanningService = Depends(get_planning_service)) -> GoalResponse:
    return GoalResponse.from_domain(service.add_goal(
        founder_id, plan_id, title=payload.title, description=payload.description,
        priority=payload.priority, target_date=payload.target_date))


@router.get("/plans/{plan_id}/goals", response_model=GoalListResponse, summary="List goals")
def list_goals(plan_id: str, founder_id: int = Depends(get_current_founder_id),
               service: PlanningService = Depends(get_planning_service)) -> GoalListResponse:
    items = service.list_goals(founder_id, plan_id)
    return GoalListResponse(goals=[GoalResponse.from_domain(g) for g in items], total=len(items))


@router.patch("/goals/{goal_id}", response_model=GoalResponse, summary="Update a goal")
def update_goal(goal_id: str, payload: GoalUpdate, founder_id: int = Depends(get_current_founder_id),
                service: PlanningService = Depends(get_planning_service)) -> GoalResponse:
    fields = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if k != "target_date"}
    fields.update(_date_kwargs(payload, "target_date", "clear_target_date"))
    return GoalResponse.from_domain(service.update_goal(founder_id, goal_id, **fields))


# --- tasks ------------------------------------------------------------------


@router.post("/goals/{goal_id}/tasks", response_model=TaskResponse, status_code=201, summary="Add a task")
def add_task(goal_id: str, payload: TaskCreate, founder_id: int = Depends(get_current_founder_id),
             service: PlanningService = Depends(get_planning_service),
             db: Session = Depends(get_db)) -> TaskResponse:
    # Saved first, synced second, and never the other way round: the task is
    # committed before Google is contacted, so no calendar failure can cost the
    # founder what they typed.
    task = service.add_task(
        founder_id, goal_id, title=payload.title, priority=payload.priority,
        due_date=payload.due_date, due_time=payload.due_time)
    task = hooks.after_task_saved(db, service, task, timezone_name=payload.timezone)
    return TaskResponse.from_domain(task)


@router.get("/goals/{goal_id}/tasks", response_model=TaskListResponse, summary="List tasks")
def list_tasks(goal_id: str, founder_id: int = Depends(get_current_founder_id),
               service: PlanningService = Depends(get_planning_service)) -> TaskListResponse:
    items = service.list_tasks(founder_id, goal_id)
    return TaskListResponse(tasks=[TaskResponse.from_domain(t) for t in items], total=len(items))


@router.patch("/tasks/{task_id}", response_model=TaskResponse, summary="Update a task")
def update_task(task_id: str, payload: TaskUpdate, founder_id: int = Depends(get_current_founder_id),
                service: PlanningService = Depends(get_planning_service),
                db: Session = Depends(get_db)) -> TaskResponse:
    fields = {k: v for k, v in payload.model_dump(exclude_unset=True).items()
              if k not in ("due_date", "due_time", "timezone")}
    fields.update(_date_kwargs(payload, "due_date", "clear_due_date"))
    fields.update(_date_kwargs(payload, "due_time", "clear_due_time"))
    task = service.update_task(founder_id, task_id, **fields)
    # Updates the existing event rather than adding a second one -- the task
    # carries the event id it created last time.
    task = hooks.after_task_saved(db, service, task, timezone_name=payload.timezone)
    return TaskResponse.from_domain(task)


@router.delete("/tasks/{task_id}", status_code=204, summary="Delete a task")
def delete_task(task_id: str, founder_id: int = Depends(get_current_founder_id),
                service: PlanningService = Depends(get_planning_service),
                db: Session = Depends(get_db)) -> None:
    # Unlike plans (archived, recoverable) a task has no restore path -- this
    # is a real row delete, so 204/no body rather than echoing back a
    # response_model for something that no longer exists.
    #
    # The event goes first, because its id lives on the task row we are about to
    # remove. If Google is unreachable the delete still proceeds and leaves one
    # orphaned calendar entry -- far better than a task that refuses to go away
    # because of someone else's outage.
    task = service.get_task(founder_id, task_id)
    hooks.before_task_deleted(db, task)
    service.delete_task(founder_id, task_id)


# --- reminders --------------------------------------------------------------


@router.post("/tasks/{task_id}/reminders", response_model=ReminderResponse, status_code=201,
             summary="Schedule a reminder for a task")
def schedule_reminder(task_id: str, payload: ReminderCreate,
                      founder_id: int = Depends(get_current_founder_id),
                      service: PlanningService = Depends(get_planning_service)) -> ReminderResponse:
    return ReminderResponse.from_domain(service.schedule_reminder(
        founder_id, task_id, remind_at=payload.remind_at, channel=payload.channel, note=payload.note))


@router.get("/reminders", response_model=ReminderListResponse, summary="List my reminders")
def list_reminders(task_id: str | None = None, founder_id: int = Depends(get_current_founder_id),
                   service: PlanningService = Depends(get_planning_service)) -> ReminderListResponse:
    items = service.list_reminders(founder_id, task_id=task_id)
    return ReminderListResponse(reminders=[ReminderResponse.from_domain(r) for r in items], total=len(items))


@router.delete("/reminders/{reminder_id}", response_model=ReminderResponse, summary="Cancel a reminder")
def cancel_reminder(reminder_id: str, founder_id: int = Depends(get_current_founder_id),
                    service: PlanningService = Depends(get_planning_service)) -> ReminderResponse:
    return ReminderResponse.from_domain(service.cancel_reminder(founder_id, reminder_id))
