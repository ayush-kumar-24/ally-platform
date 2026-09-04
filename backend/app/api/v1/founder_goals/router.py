"""Founder Goals API router -- transport only. Every endpoint resolves the
authenticated founder and delegates to FounderGoalService; ownership +
validation live in the service. Domain errors propagate to the global handler.

Gated on Feature.GOALS (Rs 450) at the router, like planning and vision --
see require_goals. This is app.founder_goals' standalone Goal, distinct from
the nested Goal inside Plan Your Day, but both now sit on the same tier: the
pricing page sells them together as the place a founder acts on their report.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.v1.founder_goals.dependencies import (
    get_current_founder_id,
    get_founder_goal_service,
    require_goals,
)
from app.api.v1.founder_goals.responses import FounderGoalListResponse, FounderGoalResponse
from app.api.v1.founder_goals.schemas import FounderGoalCreate, FounderGoalUpdate
from app.founder_goals.service import FounderGoalService

router = APIRouter(prefix="/goals", tags=["founder-goals"],
                   dependencies=[Depends(require_goals)])


@router.post("", response_model=FounderGoalResponse, status_code=201, summary="Create a goal")
def create_goal(
    payload: FounderGoalCreate,
    founder_id: int = Depends(get_current_founder_id),
    service: FounderGoalService = Depends(get_founder_goal_service),
) -> FounderGoalResponse:
    return FounderGoalResponse.from_domain(
        service.create_goal(founder_id, title=payload.title, subtitle=payload.subtitle))


@router.get("", response_model=FounderGoalListResponse, summary="List my goals")
def list_goals(
    founder_id: int = Depends(get_current_founder_id),
    service: FounderGoalService = Depends(get_founder_goal_service),
) -> FounderGoalListResponse:
    items = service.list_goals(founder_id)
    return FounderGoalListResponse(goals=[FounderGoalResponse.from_domain(g) for g in items], total=len(items))


@router.patch("/{goal_id}", response_model=FounderGoalResponse, summary="Update a goal")
def update_goal(
    goal_id: str,
    payload: FounderGoalUpdate,
    founder_id: int = Depends(get_current_founder_id),
    service: FounderGoalService = Depends(get_founder_goal_service),
) -> FounderGoalResponse:
    fields = payload.model_dump(exclude_unset=True)
    return FounderGoalResponse.from_domain(service.update_goal(founder_id, goal_id, **fields))


@router.delete("/{goal_id}", status_code=204, summary="Delete a goal")
def delete_goal(
    goal_id: str,
    founder_id: int = Depends(get_current_founder_id),
    service: FounderGoalService = Depends(get_founder_goal_service),
) -> None:
    service.delete_goal(founder_id, goal_id)
