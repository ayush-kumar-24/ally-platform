"""Admin API router (Phase 12) -- transport only.

Every endpoint resolves the current admin (role-gated), delegates to AdminService,
and maps the result to a response model. No business logic here; permission checks
and audit live in the service. Domain errors propagate to the global handler.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.admin.models import AdminUser
from app.admin.service import AdminService
from app.api.v1.admin.dependencies import get_admin_service, get_current_admin
from app.api.v1.admin.responses import (
    AnnouncementListResponse,
    AnnouncementResponse,
    AuditEventResponse,
    AuditListResponse,
    ConversationListResponse,
    ConversationResponse,
    DashboardResponse,
    FeedbackListResponse,
    FeedbackResponse,
    FounderListResponse,
    FounderResponse,
)
from app.api.v1.admin.schemas import AnnouncementCreate, StatusChangeRequest

router = APIRouter(prefix="/admin", tags=["admin"])


# --- dashboard --------------------------------------------------------------


@router.get("/dashboard", response_model=DashboardResponse, summary="System dashboard metrics")
def dashboard(admin: AdminUser = Depends(get_current_admin),
              service: AdminService = Depends(get_admin_service)) -> DashboardResponse:
    return DashboardResponse.from_domain(service.dashboard(admin))


# --- founders ---------------------------------------------------------------


@router.get("/founders", response_model=FounderListResponse, summary="List / search founders")
def list_founders(
    q: str | None = Query(default=None, description="Search by name or email"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    admin: AdminUser = Depends(get_current_admin),
    service: AdminService = Depends(get_admin_service),
) -> FounderListResponse:
    items = (service.search_founders(admin, q, limit=limit) if q
             else service.list_founders(admin, limit=limit, offset=offset))
    return FounderListResponse(founders=[FounderResponse.from_domain(f) for f in items], total=len(items))


@router.get("/founders/{founder_id}", response_model=FounderResponse, summary="Founder profile")
def get_founder(founder_id: int, admin: AdminUser = Depends(get_current_admin),
                service: AdminService = Depends(get_admin_service)) -> FounderResponse:
    return FounderResponse.from_domain(service.get_founder(admin, founder_id))


@router.post("/founders/{founder_id}/suspend", response_model=FounderResponse, summary="Suspend a founder")
def suspend_founder(founder_id: int, payload: StatusChangeRequest = StatusChangeRequest(),
                    admin: AdminUser = Depends(get_current_admin),
                    service: AdminService = Depends(get_admin_service)) -> FounderResponse:
    return FounderResponse.from_domain(service.suspend_founder(admin, founder_id, reason=payload.reason))


@router.post("/founders/{founder_id}/restore", response_model=FounderResponse, summary="Restore a founder")
def restore_founder(founder_id: int, payload: StatusChangeRequest = StatusChangeRequest(),
                    admin: AdminUser = Depends(get_current_admin),
                    service: AdminService = Depends(get_admin_service)) -> FounderResponse:
    return FounderResponse.from_domain(service.restore_founder(admin, founder_id, reason=payload.reason))


# --- conversations / feedback ----------------------------------------------


@router.get("/conversations", response_model=ConversationListResponse, summary="List conversations")
def list_conversations(
    founder_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    admin: AdminUser = Depends(get_current_admin),
    service: AdminService = Depends(get_admin_service),
) -> ConversationListResponse:
    items = service.list_conversations(admin, founder_id=founder_id, limit=limit, offset=offset)
    return ConversationListResponse(
        conversations=[ConversationResponse.from_domain(c) for c in items], total=len(items))


@router.get("/feedback", response_model=FeedbackListResponse, summary="List feedback")
def list_feedback(limit: int = Query(default=50, ge=1, le=500),
                  admin: AdminUser = Depends(get_current_admin),
                  service: AdminService = Depends(get_admin_service)) -> FeedbackListResponse:
    items = service.list_feedback(admin, limit=limit)
    return FeedbackListResponse(feedback=[FeedbackResponse.from_domain(f) for f in items], total=len(items))


# --- audit ------------------------------------------------------------------


@router.get("/audit", response_model=AuditListResponse, summary="Audit history")
def list_audit(limit: int = Query(default=100, ge=1, le=1000),
               admin: AdminUser = Depends(get_current_admin),
               service: AdminService = Depends(get_admin_service)) -> AuditListResponse:
    items = service.list_audit(admin, limit=limit)
    return AuditListResponse(events=[AuditEventResponse.from_domain(e) for e in items], total=len(items))


# --- announcements ----------------------------------------------------------


@router.get("/announcements", response_model=AnnouncementListResponse, summary="List announcements")
def list_announcements(active_only: bool = Query(default=False),
                       admin: AdminUser = Depends(get_current_admin),
                       service: AdminService = Depends(get_admin_service)) -> AnnouncementListResponse:
    items = service.list_announcements(admin, active_only=active_only)
    return AnnouncementListResponse(
        announcements=[AnnouncementResponse.from_domain(a) for a in items], total=len(items))


@router.post("/announcements", response_model=AnnouncementResponse, status_code=201,
             summary="Publish an announcement")
def create_announcement(payload: AnnouncementCreate,
                        admin: AdminUser = Depends(get_current_admin),
                        service: AdminService = Depends(get_admin_service)) -> AnnouncementResponse:
    announcement = service.publish_announcement(
        admin, title=payload.title, body=payload.body, audience=payload.audience)
    return AnnouncementResponse.from_domain(announcement)
