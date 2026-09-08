"""Founder Goals API router -- transport only. Every endpoint resolves the
authenticated founder and delegates to FounderGoalService; ownership +
validation live in the service. Domain errors propagate to the global handler.

Gated on Feature.GOALS (Rs 499) at the router -- see
app/api/v1/entitlement_gates.py. This said "no plan-gate dependency: Goals is
a free feature", which was true only while Free carried nearly the whole
product for our own testers. Once PUBLIC_LAUNCH empties the Free tier, an
ungated router here serves a founder who has bought nothing. Note that GOALS
is a separate feature from PLAN_YOUR_DAY, which app.planning's nested Goal
belongs to; both are Rs 499, gated in different places.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.v1.founder_goals.dependencies import get_current_founder_id, get_founder_goal_service
from app.api.v1.founder_goals.responses import FounderGoalListResponse, FounderGoalResponse
from app.api.v1.founder_goals.schemas import FounderGoalCreate, FounderGoalUpdate
from app.founder_goals.service import FounderGoalService
from app.api.v1.entitlement_gates import require_goals

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
    # `completed` is a state change with a side effect, not a text field, so it
    # is pulled out rather than passed into update_goal. Text first: a request
    # that renames a goal AND completes it should put the new title on the
    # achievement, not the old one.
    completed = fields.pop("completed", None)
    goal = service.update_goal(founder_id, goal_id, **fields) if fields else None
    if completed is not None:
        goal = service.set_completed(founder_id, goal_id, completed)
    if goal is None:
        goal = service.update_goal(founder_id, goal_id)
    return FounderGoalResponse.from_domain(goal)


@router.delete("/{goal_id}", status_code=204, summary="Delete a goal")
def delete_goal(
    goal_id: str,
    founder_id: int = Depends(get_current_founder_id),
    service: FounderGoalService = Depends(get_founder_goal_service),
) -> None:
    service.delete_goal(founder_id, goal_id)
