"""Achievements API router -- transport only. Every endpoint resolves the
authenticated founder and delegates to AchievementService; ownership,
validation, and the engagement gate all live in the service. Domain errors
propagate to the global handler (AchievementsLockedError -> 403).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.achievements.service import AchievementService
from app.api.v1.achievements.dependencies import get_achievement_service, get_current_founder_id
from app.api.v1.achievements.responses import (
    AchievementListResponse,
    AchievementResponse,
    EngagementResponse,
)
from app.api.v1.achievements.schemas import AchievementCreate, AchievementUpdate

router = APIRouter(prefix="/achievements", tags=["achievements"])


@router.get("/engagement", response_model=EngagementResponse,
            summary="Real Ally-conversation engagement + whether Achievements is unlocked")
def get_engagement(
    founder_id: int = Depends(get_current_founder_id),
    service: AchievementService = Depends(get_achievement_service),
) -> EngagementResponse:
    return EngagementResponse.from_domain(service.get_engagement(founder_id))


@router.post("", response_model=AchievementResponse, status_code=201, summary="Add an achievement")
def create_achievement(
    payload: AchievementCreate,
    founder_id: int = Depends(get_current_founder_id),
    service: AchievementService = Depends(get_achievement_service),
) -> AchievementResponse:
    return AchievementResponse.from_domain(service.create_achievement(
        founder_id, title=payload.title, description=payload.description,
        category=payload.category, occurred_on=payload.occurred_on))


@router.get("", response_model=AchievementListResponse, summary="List my achievements")
def list_achievements(
    founder_id: int = Depends(get_current_founder_id),
    service: AchievementService = Depends(get_achievement_service),
) -> AchievementListResponse:
    items = service.list_achievements(founder_id)
    return AchievementListResponse(
        achievements=[AchievementResponse.from_domain(a) for a in items], total=len(items))


@router.patch("/{achievement_id}", response_model=AchievementResponse, summary="Update an achievement")
def update_achievement(
    achievement_id: str,
    payload: AchievementUpdate,
    founder_id: int = Depends(get_current_founder_id),
    service: AchievementService = Depends(get_achievement_service),
) -> AchievementResponse:
    fields = payload.model_dump(exclude_unset=True)
    return AchievementResponse.from_domain(service.update_achievement(founder_id, achievement_id, **fields))


@router.delete("/{achievement_id}", status_code=204, summary="Delete an achievement")
def delete_achievement(
    achievement_id: str,
    founder_id: int = Depends(get_current_founder_id),
    service: AchievementService = Depends(get_achievement_service),
) -> None:
    service.delete_achievement(founder_id, achievement_id)
