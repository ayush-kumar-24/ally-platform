"""Framework Usage API router -- transport only. Every endpoint resolves the
authenticated founder and delegates to FrameworkUsageService; validation
lives in the service. Domain errors propagate to the global handler.

Free feature, available immediately -- no plan-gate dependency, same as
app/api/v1/founder_goals/router.py and app/api/v1/vision/router.py.

Prefix is /frameworks (not /framework-usage) to match the proposal's
endpoint shapes (GET /frameworks/usage, POST /frameworks/{id}/use, PUT
/frameworks/{id}/note) -- the framework CONTENT stays frontend-only, so
there's no separate app.api.v1.frameworks router this would collide with.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.v1.framework_usage.dependencies import get_current_founder_id, get_framework_usage_service
from app.api.v1.framework_usage.responses import FrameworkUsageEntry, FrameworkUsageResponse, usage_map_from_domain
from app.api.v1.framework_usage.schemas import FrameworkNoteUpdate
from app.framework_usage.service import FrameworkUsageService

router = APIRouter(prefix="/frameworks", tags=["framework-usage"])


@router.get("/usage", response_model=dict[str, FrameworkUsageEntry], summary="My framework usage + notes")
def get_usage(
    founder_id: int = Depends(get_current_founder_id),
    service: FrameworkUsageService = Depends(get_framework_usage_service),
) -> dict[str, FrameworkUsageEntry]:
    return usage_map_from_domain(service.list_usage(founder_id))


@router.post("/{framework_id}/use", response_model=FrameworkUsageResponse, summary="Record opening a framework")
def record_used(
    framework_id: str,
    founder_id: int = Depends(get_current_founder_id),
    service: FrameworkUsageService = Depends(get_framework_usage_service),
) -> FrameworkUsageResponse:
    return FrameworkUsageResponse.from_domain(service.record_used(founder_id, framework_id))


@router.put("/{framework_id}/note", response_model=FrameworkUsageResponse, summary="Save/clear my note")
def save_note(
    framework_id: str,
    payload: FrameworkNoteUpdate,
    founder_id: int = Depends(get_current_founder_id),
    service: FrameworkUsageService = Depends(get_framework_usage_service),
) -> FrameworkUsageResponse:
    return FrameworkUsageResponse.from_domain(service.save_note(founder_id, framework_id, payload.note))
