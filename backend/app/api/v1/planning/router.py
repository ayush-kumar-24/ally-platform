"""Planning API router -- transport only. Every endpoint resolves the authenticated
founder and delegates to PlanningService; ownership + validation live in the service.
Domain errors propagate to the global handler."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.v1.planning.dependencies import (
    get_current_founder_id,
    get_diagnosis_steps,
    get_planning_service,
)
from app.api.v1.planning.responses import (
    GoalListResponse,
    GoalResponse,
    GoalWithTasksResponse,
    PlanDetailResponse,
    PlanListResponse,
    PlanResponse,
    TaskListResponse,
    TaskResponse,
)
from app.api.v1.planning.schemas import (
    GoalCreate,
    GoalUpdate,
    PlanCreate,
    PlanUpdate,
    TaskCreate,
    TaskUpdate,
)
from app.planning.service import PlanningService

router = APIRouter(prefix="/planning", tags=["planning"])


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
             service: PlanningService = Depends(get_planning_service)) -> TaskResponse:
    return TaskResponse.from_domain(service.add_task(
        founder_id, goal_id, title=payload.title, priority=payload.priority, due_date=payload.due_date))


@router.get("/goals/{goal_id}/tasks", response_model=TaskListResponse, summary="List tasks")
def list_tasks(goal_id: str, founder_id: int = Depends(get_current_founder_id),
               service: PlanningService = Depends(get_planning_service)) -> TaskListResponse:
    items = service.list_tasks(founder_id, goal_id)
    return TaskListResponse(tasks=[TaskResponse.from_domain(t) for t in items], total=len(items))


@router.patch("/tasks/{task_id}", response_model=TaskResponse, summary="Update a task")
def update_task(task_id: str, payload: TaskUpdate, founder_id: int = Depends(get_current_founder_id),
                service: PlanningService = Depends(get_planning_service)) -> TaskResponse:
    fields = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if k != "due_date"}
    fields.update(_date_kwargs(payload, "due_date", "clear_due_date"))
    return TaskResponse.from_domain(service.update_task(founder_id, task_id, **fields))
