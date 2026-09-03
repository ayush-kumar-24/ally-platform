"""Admin Panel endpoints -- transport only; every rule lives in AdminPanelService.

    GET    /admin/me                       caller's role + capabilities
    GET    /admin/dashboard-metrics        total users, Live now / Today / 7 days, and the rest
    GET    /admin/users                    search / filter / sort / paginate
    GET    /admin/users/{id}               full detail
    PATCH  /admin/users/{id}               partial update (per-field authorization)
    POST   /admin/users/{id}/status        activate / deactivate / suspend / ban
    POST   /admin/users/{id}/reset-diagnosis
    POST   /admin/users/{id}/reset-conversations
    DELETE /admin/users/{id}               soft-delete (ban)
    GET    /admin/users/{id}/credits       ledger for one user
    POST   /admin/users/{id}/credits       adjust credits (Super Admin only)
    PATCH  /admin/users/{id}/subscription  plan / expiry / credit grants
    GET    /admin/privacy-requests         DSAR review queue (view_data, correct_data, ...)
    PATCH  /admin/privacy-requests/{id}    resolve a queued request
    GET    /admin/audit-log               immutable audit trail

Named /audit-log, not /audit: the Phase 12 admin router already owns GET /admin/audit
and is registered first, so a second /audit here would be silently shadowed and never
reached. Distinct paths keep both endpoints usable.

Every route depends on `get_panel_admin`, so an unauthenticated or non-admin caller
is rejected before any handler body runs. There is no route here without it.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query

from app.admin.rbac import capabilities_for
from app.admin.users_models import (
    ConsentStatus,
    SortField,
    UserFilters,
    UserStatus,
)
from app.api.v1.admin.panel_dependencies import (
    PanelAdmin,
    client_ip,
    get_panel_admin,
    get_panel_service,
)
from app.api.v1.admin.panel_responses import (
    AuditEventResponse,
    AuditPageResponse,
    CreditAdjustResponse,
    CreditLedgerResponse,
    CreditTransactionResponse,
    DashboardMetricsResponse,
    PrivacyRequestListResponse,
    PrivacyRequestResponse,
    UserDetailResponse,
    UserPageResponse,
    UserSummaryResponse,
    WhoAmIResponse,
)
from app.api.v1.admin.panel_schemas import (
    ConfirmRequest,
    CreditAdjustRequest,
    PrivacyRequestResolveRequest,
    StatusChangeRequest,
    SubscriptionUpdateRequest,
    UserUpdateRequest,
)
from app.middleware.error_handler import AppError

router = APIRouter(prefix="/admin", tags=["admin-panel"])


class ConfirmationRequiredError(AppError):
    def __init__(self, action: str):
        super().__init__(f"This {action} must be confirmed explicitly.", status_code=422)


@router.get("/me", response_model=WhoAmIResponse, summary="Caller's admin role and capabilities")
def whoami(admin: PanelAdmin = Depends(get_panel_admin)) -> WhoAmIResponse:
    return WhoAmIResponse(admin_id=admin.admin_id, email=admin.email,
                          role=admin.role.value, capabilities=capabilities_for(admin.role))


@router.get("/dashboard-metrics", response_model=DashboardMetricsResponse,
           summary="Dashboard cards: total users, Live now / Today / 7 days, and the rest")
def dashboard_metrics(admin: PanelAdmin = Depends(get_panel_admin),
                      service=Depends(get_panel_service)) -> DashboardMetricsResponse:
    """Named /dashboard-metrics, not /dashboard: the Phase 12 admin router
    already owns GET /admin/dashboard and is registered first, so a second
    /dashboard here would be silently shadowed and never reached -- the exact
    collision /audit-log below was already named around."""
    return DashboardMetricsResponse.from_domain(service.dashboard_metrics(admin))


# --- users ------------------------------------------------------------------

@router.get("/users", response_model=UserPageResponse, summary="Search / list users")
def list_users(
    search: str | None = Query(default=None, max_length=200,
                               description="Matches name, email, phone, business name or founder id"),
    status: UserStatus | None = Query(default=None),
    subscription: str | None = Query(default=None, max_length=30),
    registered_after: datetime | None = Query(default=None),
    registered_before: datetime | None = Query(default=None),
    active_since: datetime | None = Query(default=None),
    diagnosis_completed: bool | None = Query(default=None),
    consent_status: ConsentStatus | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    sort_by: SortField = Query(default=SortField.CREATED_AT),
    descending: bool = Query(default=True),
    admin: PanelAdmin = Depends(get_panel_admin),
    service=Depends(get_panel_service),
) -> UserPageResponse:
    filters = UserFilters(
        search=search, status=status, subscription=subscription,
        registered_after=registered_after, registered_before=registered_before,
        active_since=active_since, diagnosis_completed=diagnosis_completed,
        consent_status=consent_status)
    return UserPageResponse.from_domain(service.list_users(
        admin, filters=filters, page=page, page_size=page_size,
        sort_by=sort_by, descending=descending))


@router.get("/users/{founder_id}", response_model=UserDetailResponse, summary="User detail")
def get_user(founder_id: int, admin: PanelAdmin = Depends(get_panel_admin),
             service=Depends(get_panel_service)) -> UserDetailResponse:
    return UserDetailResponse.from_domain(service.get_user(admin, founder_id))


@router.patch("/users/{founder_id}", response_model=UserSummaryResponse,
              summary="Update a user (each field authorized separately)")
def update_user(founder_id: int, payload: UserUpdateRequest,
                ip: str | None = Depends(client_ip),
                admin: PanelAdmin = Depends(get_panel_admin),
                service=Depends(get_panel_service)) -> UserSummaryResponse:
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    return UserSummaryResponse.from_domain(service.update_user(admin, founder_id, changes, ip=ip))


@router.post("/users/{founder_id}/status", response_model=UserSummaryResponse,
             summary="Activate / deactivate / suspend / ban")
def change_status(founder_id: int, payload: StatusChangeRequest,
                  ip: str | None = Depends(client_ip),
                  admin: PanelAdmin = Depends(get_panel_admin),
                  service=Depends(get_panel_service)) -> UserSummaryResponse:
    return UserSummaryResponse.from_domain(
        service.set_status(admin, founder_id, payload.status, reason=payload.reason, ip=ip))


@router.post("/users/{founder_id}/reset-diagnosis", response_model=dict,
             summary="Reset the user's diagnosis progress")
def reset_diagnosis(founder_id: int, payload: ConfirmRequest,
                    ip: str | None = Depends(client_ip),
                    admin: PanelAdmin = Depends(get_panel_admin),
                    service=Depends(get_panel_service)) -> dict:
    if not payload.confirm:
        raise ConfirmationRequiredError("diagnosis reset")
    return {"founder_id": founder_id,
            "rows_affected": service.reset_diagnosis(admin, founder_id, ip=ip)}


@router.post("/users/{founder_id}/reset-conversations", response_model=dict,
             summary="Delete the user's chat history")
def reset_conversations(founder_id: int, payload: ConfirmRequest,
                        ip: str | None = Depends(client_ip),
                        admin: PanelAdmin = Depends(get_panel_admin),
                        service=Depends(get_panel_service)) -> dict:
    if not payload.confirm:
        raise ConfirmationRequiredError("conversation reset")
    return {"founder_id": founder_id,
            "rows_affected": service.reset_conversations(admin, founder_id, ip=ip)}


@router.post("/users/{founder_id}/cancel-deletion", response_model=dict,
             summary="Cancel a founder's pending account erasure")
def cancel_pending_deletion(founder_id: int, payload: ConfirmRequest,
                            ip: str | None = Depends(client_ip),
                            admin: PanelAdmin = Depends(get_panel_admin),
                            service=Depends(get_panel_service)) -> dict:
    """For the one case a founder cannot cancel their own pending deletion via
    the Privacy Center: a Supabase-webhook-triggered erasure, where their
    identity is already gone and they can only reach support out-of-band.
    `reason` is required here (not just `confirm`) -- reversing an erasure
    request needs a human explanation on the record, not just a checkbox."""
    if not payload.confirm:
        raise ConfirmationRequiredError("deletion cancellation")
    if not payload.reason:
        raise ConfirmationRequiredError("deletion cancellation (reason required)")
    state = service.cancel_pending_deletion(admin, founder_id, reason=payload.reason, ip=ip)
    return {"founder_id": founder_id, "deletion_pending": state.deletion_pending}


@router.delete("/users/{founder_id}", response_model=UserSummaryResponse,
               summary="Delete a user (soft-delete / ban)")
def delete_user(founder_id: int, payload: ConfirmRequest,
                ip: str | None = Depends(client_ip),
                admin: PanelAdmin = Depends(get_panel_admin),
                service=Depends(get_panel_service)) -> UserSummaryResponse:
    if not payload.confirm:
        raise ConfirmationRequiredError("user deletion")
    return UserSummaryResponse.from_domain(
        service.delete_user(admin, founder_id, reason=payload.reason, ip=ip))


# --- credits ----------------------------------------------------------------

@router.get("/users/{founder_id}/credits", response_model=CreditLedgerResponse,
            summary="Credit ledger for one user")
def list_credits(founder_id: int,
                 limit: int = Query(default=50, ge=1, le=200),
                 offset: int = Query(default=0, ge=0),
                 admin: PanelAdmin = Depends(get_panel_admin),
                 service=Depends(get_panel_service)) -> CreditLedgerResponse:
    items, total = service.list_credit_transactions(admin, founder_id,
                                                    limit=limit, offset=offset)
    balance = service.credits.get_balance(founder_id).balance
    return CreditLedgerResponse(
        items=[CreditTransactionResponse.from_domain(t) for t in items],
        total=total, balance=balance)


@router.post("/users/{founder_id}/credits", response_model=CreditAdjustResponse,
             status_code=201, summary="Adjust credits (Super Admin only)")
def adjust_credits(founder_id: int, payload: CreditAdjustRequest,
                   ip: str | None = Depends(client_ip),
                   admin: PanelAdmin = Depends(get_panel_admin),
                   service=Depends(get_panel_service)) -> CreditAdjustResponse:
    tx = service.adjust_credits(admin, founder_id, operation=payload.operation,
                                amount=payload.amount, reason=payload.reason, ip=ip)
    return CreditAdjustResponse(
        transaction=CreditTransactionResponse.from_domain(tx),
        balance=tx.balance_after,
        message=(f"{payload.operation.value.upper()} applied. "
                 f"Balance {tx.balance_before} -> {tx.balance_after}."))


# --- subscription -----------------------------------------------------------

@router.patch("/users/{founder_id}/subscription", response_model=dict,
              summary="Change plan / expiry / credit grants (Super Admin only)")
def update_subscription(founder_id: int, payload: SubscriptionUpdateRequest,
                        ip: str | None = Depends(client_ip),
                        admin: PanelAdmin = Depends(get_panel_admin),
                        service=Depends(get_panel_service)) -> dict:
    return service.update_subscription(
        admin, founder_id, plan=payload.plan, expires_at=payload.expires_at,
        monthly_credits=payload.monthly_credits, bonus_credits=payload.bonus_credits, ip=ip)


# --- privacy requests (DSAR review queue) ------------------------------------

@router.get("/privacy-requests", response_model=PrivacyRequestListResponse,
            summary="DSAR review queue -- view_data, correct_data and every other logged request")
def list_privacy_requests(
    status: str | None = Query(default=None, max_length=20,
                               description="Filter by pending / in_progress / completed / rejected"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    admin: PanelAdmin = Depends(get_panel_admin),
    service=Depends(get_panel_service),
) -> PrivacyRequestListResponse:
    items = service.list_privacy_requests(admin, status=status, limit=limit, offset=offset)
    return PrivacyRequestListResponse.from_domain(items)


@router.patch("/privacy-requests/{request_id}", response_model=PrivacyRequestResponse,
              summary="Resolve a queued Privacy Center request")
def resolve_privacy_request(
    request_id: int, payload: PrivacyRequestResolveRequest,
    ip: str | None = Depends(client_ip),
    admin: PanelAdmin = Depends(get_panel_admin),
    service=Depends(get_panel_service),
) -> PrivacyRequestResponse:
    if payload.status == "rejected" and not payload.rejection_reason:
        raise ConfirmationRequiredError("rejection (rejection_reason required)")
    updated = service.resolve_privacy_request(
        admin, request_id, status=payload.status,
        processing_notes=payload.processing_notes,
        rejection_reason=payload.rejection_reason, ip=ip)
    return PrivacyRequestResponse.from_domain(updated)


# --- audit ------------------------------------------------------------------

@router.get("/audit-log", response_model=AuditPageResponse, summary="Immutable audit trail")
def list_audit(limit: int = Query(default=100, ge=1, le=500),
               offset: int = Query(default=0, ge=0),
               target_user_id: int | None = Query(default=None),
               action: str | None = Query(default=None, max_length=80),
               admin: PanelAdmin = Depends(get_panel_admin),
               service=Depends(get_panel_service)) -> AuditPageResponse:
    items, total = service.list_audit(admin, limit=limit, offset=offset,
                                      target_user_id=target_user_id, action=action)
    return AuditPageResponse(items=[AuditEventResponse.from_domain(e) for e in items],
                             total=total, limit=limit, offset=offset)
