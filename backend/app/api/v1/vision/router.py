"""Vision API router -- transport only. Every endpoint resolves the
authenticated founder and delegates to VisionService; validation lives in
the service. Domain errors propagate to the global handler.

Free feature, available immediately -- no plan-gate dependency, same as
app/api/v1/founder_goals/router.py.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.v1.vision.dependencies import get_current_founder_id, get_vision_service
from app.api.v1.vision.responses import VisionResponse, VisionSummaryResponse, VisionTerritoryResponse
from app.api.v1.vision.schemas import VisionSummaryUpdate, VisionTerritoryUpdate
from app.vision.service import VisionService

router = APIRouter(prefix="/vision", tags=["vision"])


@router.get("", response_model=VisionResponse, summary="Get my vision")
def get_vision(
    founder_id: int = Depends(get_current_founder_id),
    service: VisionService = Depends(get_vision_service),
) -> VisionResponse:
    return VisionResponse.from_domain(service.get_territories(founder_id), service.get_summary(founder_id))


@router.put("/territories/{territory_key}", response_model=VisionTerritoryResponse, summary="Save one vision territory")
def upsert_territory(
    territory_key: str,
    payload: VisionTerritoryUpdate,
    founder_id: int = Depends(get_current_founder_id),
    service: VisionService = Depends(get_vision_service),
) -> VisionTerritoryResponse:
    t = service.upsert_territory(
        founder_id, territory_key, statement=payload.statement, tag1=payload.tag1, tag2=payload.tag2)
    return VisionTerritoryResponse.from_domain(territory_key, t)


@router.put("/summary", response_model=VisionSummaryResponse, summary="Save my vision summary")
def upsert_summary(
    payload: VisionSummaryUpdate,
    founder_id: int = Depends(get_current_founder_id),
    service: VisionService = Depends(get_vision_service),
) -> VisionSummaryResponse:
    fields = payload.model_dump(exclude_unset=True)
    s = service.upsert_summary(founder_id, **fields)
    return VisionSummaryResponse.from_domain(s)
