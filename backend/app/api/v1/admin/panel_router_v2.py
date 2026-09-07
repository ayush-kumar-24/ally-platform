"""Admin Panel, second wave -- bulk credits, flags, broadcasts, metrics, timeline,
conversation viewer, report regeneration.

Kept in its own module so the original panel_router stays readable; both are mounted
under the same /admin prefix with distinct paths.

    POST   /admin/credits/bulk              cohort credit operation (Super Admin)
    GET    /admin/metrics                   dashboard cards
    GET    /admin/users/{id}/timeline       chronological history
    GET    /admin/users/{id}/conversations  list (Support may view)
    GET    /admin/conversations/{cid}       read-only transcript
    GET    /admin/founder-feedback          star ratings + written notes (Support may view)
    GET    /admin/founder-feedback/stats    counts + average rating

Named /founder-feedback, not /feedback: the Phase 12 admin router (app/api/v1/
admin/router.py) already owns GET /admin/feedback, registered earlier in
router.py, so a second /admin/feedback here would be silently shadowed and
never reached -- the exact same collision /admin/audit-log below was already
renamed to avoid. That older route also targets a different, never-built
"suggestion feedback" shape (FeedbackSummary has a suggestion_id, not
rating/outcome_text), not the real founder_feedback table this reads.
    POST   /admin/users/{id}/regenerate-report
    GET    /admin/flags                     list feature flags
    PUT    /admin/flags/{key}               set a global flag (Super Admin)
    PUT    /admin/flags/{key}/users/{id}    per-founder override (Super Admin)
    GET    /admin/broadcasts                list
    POST   /admin/broadcasts                publish (Super Admin)
    DELETE /admin/broadcasts/{id}           deactivate (Super Admin)
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict, Field

from app.admin.broadcasts import Audience, Severity
from app.admin.rbac import Capability, require
from app.admin.users_models import UserFilters, UserStatus
from app.api.v1.admin.panel_dependencies import (
    PanelAdmin,
    client_ip,
    get_panel_admin,
    get_panel_service,
)
from app.api.v1.admin.panel_schemas import ConfirmRequest
from app.core.container import container
from app.credits.models import CreditOperation
from app.core.logger import logger
from app.db.session import get_db
from app.middleware.error_handler import AppError

router = APIRouter(prefix="/admin", tags=["admin-panel"])


class NotConfiguredError(AppError):
    def __init__(self, what: str):
        super().__init__(f"{what} is not configured in this environment.", status_code=503)


# --- schemas ----------------------------------------------------------------

class BulkCreditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: CreditOperation
    amount: int = Field(ge=0, le=1_000_000)
    reason: str = Field(min_length=1, max_length=500)
    founder_ids: list[int] | None = Field(default=None, max_length=5000)
    # Cohort filters -- mutually exclusive with founder_ids (enforced in the service).
    subscription: str | None = Field(default=None, max_length=30)
    status: UserStatus | None = None
    dry_run: bool = False


class FlagRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    description: str = Field(default="", max_length=500)


class OverrideRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # null clears the override so the founder falls back to the global value.
    enabled: bool | None = None


class BroadcastRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=5000)
    severity: Severity = Severity.INFO
    audience: Audience = Audience.ALL
    audience_plan: str | None = Field(default=None, max_length=30)
    starts_at: datetime | None = None
    ends_at: datetime | None = None


# --- bulk credits -----------------------------------------------------------

@router.post("/credits/bulk", response_model=dict,
             summary="Apply a credit operation to a cohort (Super Admin only)")
def bulk_credits(payload: BulkCreditRequest, ip: str | None = Depends(client_ip),
                 admin: PanelAdmin = Depends(get_panel_admin),
                 service=Depends(get_panel_service)) -> dict:
    filters = None
    if payload.founder_ids is None:
        filters = UserFilters(subscription=payload.subscription, status=payload.status)
    return service.bulk_adjust_credits(
        admin, operation=payload.operation, amount=payload.amount, reason=payload.reason,
        founder_ids=payload.founder_ids, filters=filters, dry_run=payload.dry_run, ip=ip)


# --- metrics / timeline -----------------------------------------------------

@router.get("/metrics", response_model=dict, summary="Dashboard metric cards")
def metrics(admin: PanelAdmin = Depends(get_panel_admin), db=Depends(get_db)) -> dict:
    require(admin.role, Capability.VIEW_USERS)
    cards = container.insights_service(db).dashboard_metrics()
    return {"metrics": [
        {"key": m.key, "label": m.label, "value": m.value, "unit": m.unit,
         "available": m.available, "unavailable_reason": m.unavailable_reason}
        for m in cards]}


@router.get("/users/{founder_id}/timeline", response_model=dict,
            summary="Chronological history for a user")
def timeline(founder_id: int, limit: int = Query(default=200, ge=1, le=500),
             admin: PanelAdmin = Depends(get_panel_admin), db=Depends(get_db)) -> dict:
    require(admin.role, Capability.VIEW_USERS)
    events = container.insights_service(db).user_timeline(founder_id, limit=limit)
    return {"founder_id": founder_id, "total": len(events), "events": [
        {"at": e.at, "kind": e.kind, "title": e.title, "detail": e.detail, "meta": e.meta}
        for e in events]}


# --- conversation viewer ----------------------------------------------------

@router.get("/users/{founder_id}/conversations", response_model=dict,
            summary="List a user's conversations (read-only)")
def list_conversations(founder_id: int, limit: int = Query(default=50, ge=1, le=200),
                       offset: int = Query(default=0, ge=0),
                       admin: PanelAdmin = Depends(get_panel_admin),
                       service=Depends(get_panel_service)) -> dict:
    if service.conversations is None:
        raise NotConfiguredError("Conversation viewing")
    items, total = service.list_conversations(admin, founder_id, limit=limit, offset=offset)
    return {"total": total, "items": [
        {"conversation_id": c.conversation_id, "title": c.title,
         "created_at": c.created_at, "message_count": c.message_count} for c in items]}


@router.get("/conversations/{conversation_id}", response_model=dict,
            summary="Read a conversation transcript (read-only)")
def view_conversation(conversation_id: str,
                      admin: PanelAdmin = Depends(get_panel_admin),
                      service=Depends(get_panel_service)) -> dict:
    if service.conversations is None:
        raise NotConfiguredError("Conversation viewing")
    view = service.view_conversation(admin, conversation_id)
    if view is None:
        return {"conversation_id": conversation_id, "found": False, "messages": []}
    return {"conversation_id": view.conversation_id, "founder_id": view.founder_id,
            "title": view.title, "created_at": view.created_at, "found": True,
            "message_count": view.message_count,
            "messages": [{"message_id": m.message_id, "role": m.role,
                          "content": m.content, "created_at": m.created_at}
                         for m in view.messages]}


# --- feedback (read-only) ----------------------------------------------------

@router.get("/founder-feedback", response_model=dict,
            summary="Star ratings and written notes from founders (read-only)")
def list_feedback(feedback_type: str | None = Query(default=None, max_length=30),
                  limit: int = Query(default=50, ge=1, le=200),
                  offset: int = Query(default=0, ge=0),
                  admin: PanelAdmin = Depends(get_panel_admin),
                  service=Depends(get_panel_service)) -> dict:
    if service.feedback is None:
        raise NotConfiguredError("Feedback review")
    items, total = service.list_feedback(
        admin, feedback_type=feedback_type, limit=limit, offset=offset)
    return {"total": total, "items": [
        {"feedback_id": f.feedback_id, "founder_id": f.founder_id,
         "founder_name": f.founder_name, "founder_email": f.founder_email,
         "feedback_type": f.feedback_type, "rating": f.rating, "comment": f.comment,
         "session_id": f.session_id, "report_id": f.report_id,
         "collected_at": f.collected_at} for f in items]}


@router.get("/founder-feedback/stats", response_model=dict,
            summary="Feedback counts and average rating")
def feedback_stats(feedback_type: str | None = Query(default=None, max_length=30),
                   admin: PanelAdmin = Depends(get_panel_admin),
                   service=Depends(get_panel_service)) -> dict:
    if service.feedback is None:
        raise NotConfiguredError("Feedback review")
    stats = service.feedback_stats(admin, feedback_type=feedback_type)
    return {"total": stats.total, "rated_count": stats.rated_count,
            "average_rating": stats.average_rating, "by_type": stats.by_type}


# --- support bot misses (read-only) -----------------------------------------

@router.get("/support-misses", response_model=dict,
            summary="Questions the help bot could not answer")
def list_support_misses(limit: int = Query(default=100, ge=1, le=500),
                        admin: PanelAdmin = Depends(get_panel_admin),
                        db: Session = Depends(get_db)) -> dict:
    """Grouped by question, most-asked first.

    Grouped rather than listed: fifteen founders asking the same thing is one
    answer to write, and a flat list buries that under whatever was asked most
    recently. `founders` counts distinct people, not repeats -- one founder
    trying the same phrasing five times is not five founders wanting it.

    VIEW_USERS, not a new capability. This is aggregate product feedback about
    our own help content, at the same tier as the rest of the read-only panel.
    """
    require(admin.role, Capability.VIEW_USERS)
    try:
        rows = db.execute(text("""
            select question,
                   count(*)                  as times_asked,
                   count(distinct founder_id) as founders,
                   max(asked_at)             as last_asked,
                   max(reason)               as reason
              from support_bot_misses
             group by question
             order by times_asked desc, last_asked desc
             limit :limit
        """), {"limit": limit}).fetchall()
    except SQLAlchemyError:
        # Table absent on a target that has not run the migration. An empty
        # panel is a better answer than a 500 on a read-only review screen.
        logger.warning("support_bot_misses unavailable", exc_info=True)
        return {"total": 0, "items": []}
    return {"total": len(rows), "items": [
        {"question": r[0], "times_asked": r[1], "founders": r[2],
         "last_asked": r[3], "reason": r[4]} for r in rows]}


# --- report regeneration ----------------------------------------------------

@router.post("/users/{founder_id}/regenerate-report", response_model=dict,
             summary="Re-run report generation for a user")
def regenerate_report(founder_id: int, payload: ConfirmRequest,
                      ip: str | None = Depends(client_ip),
                      admin: PanelAdmin = Depends(get_panel_admin),
                      service=Depends(get_panel_service)) -> dict:
    if not payload.confirm:
        raise AppError("Report regeneration must be confirmed explicitly.", status_code=422)
    return service.regenerate_report(admin, founder_id, reason=payload.reason, ip=ip)


# --- feature flags ----------------------------------------------------------

@router.get("/flags", response_model=dict, summary="List feature flags")
def list_flags(admin: PanelAdmin = Depends(get_panel_admin), db=Depends(get_db)) -> dict:
    require(admin.role, Capability.VIEW_USERS)
    flags = container.feature_flag_service(db).list_flags()
    return {"flags": [{"key": f.key, "enabled": f.enabled, "description": f.description,
                       "updated_at": f.updated_at, "updated_by": f.updated_by}
                      for f in flags]}


@router.put("/flags/{key}", response_model=dict, summary="Set a global flag (Super Admin)")
def set_flag(key: str, payload: FlagRequest, ip: str | None = Depends(client_ip),
             admin: PanelAdmin = Depends(get_panel_admin),
             service=Depends(get_panel_service), db=Depends(get_db)) -> dict:
    require(admin.role, Capability.SYSTEM_SETTINGS)
    flags = container.feature_flag_service(db)
    before = flags.get_flag_enabled(key) if hasattr(flags, "get_flag_enabled") else None
    flag = flags.set_flag(key, enabled=payload.enabled, description=payload.description,
                          admin_id=admin.admin_id)
    service.audit.record(admin=admin, action="flag.set", resource=f"flag:{key}",
                         ip_address=ip, old_value={"enabled": before},
                         new_value={"enabled": flag.enabled})
    return {"key": flag.key, "enabled": flag.enabled, "description": flag.description}


@router.put("/flags/{key}/users/{founder_id}", response_model=dict,
            summary="Per-founder flag override (Super Admin)")
def set_flag_override(key: str, founder_id: int, payload: OverrideRequest,
                      ip: str | None = Depends(client_ip),
                      admin: PanelAdmin = Depends(get_panel_admin),
                      service=Depends(get_panel_service), db=Depends(get_db)) -> dict:
    require(admin.role, Capability.SYSTEM_SETTINGS)
    flags = container.feature_flag_service(db)
    flags.set_override(key, founder_id, enabled=payload.enabled, admin_id=admin.admin_id)
    service.audit.record(admin=admin, action="flag.override", resource=f"flag:{key}",
                         target_user_id=founder_id, ip_address=ip,
                         new_value={"enabled": payload.enabled})
    return {"key": key, "founder_id": founder_id, "enabled": payload.enabled,
            "resolved": flags.is_enabled(key, founder_id=founder_id)}


# --- broadcasts -------------------------------------------------------------

@router.get("/broadcasts", response_model=dict, summary="List broadcasts")
def list_broadcasts(include_inactive: bool = Query(default=True),
                    admin: PanelAdmin = Depends(get_panel_admin),
                    db=Depends(get_db)) -> dict:
    require(admin.role, Capability.VIEW_USERS)
    rows = container.broadcast_service(db).list_all(include_inactive=include_inactive)
    return {"total": len(rows), "items": [
        {"broadcast_id": b.broadcast_id, "title": b.title, "body": b.body,
         "severity": b.severity.value, "audience": b.audience.value,
         "audience_plan": b.audience_plan, "starts_at": b.starts_at, "ends_at": b.ends_at,
         "active": b.active, "created_at": b.created_at} for b in rows]}


@router.post("/broadcasts", response_model=dict, status_code=201,
             summary="Publish a broadcast (Super Admin)")
def create_broadcast(payload: BroadcastRequest, ip: str | None = Depends(client_ip),
                     admin: PanelAdmin = Depends(get_panel_admin),
                     service=Depends(get_panel_service), db=Depends(get_db)) -> dict:
    require(admin.role, Capability.SYSTEM_SETTINGS)
    b = container.broadcast_service(db).create(
        admin_id=admin.admin_id, title=payload.title, body=payload.body,
        severity=payload.severity, audience=payload.audience,
        audience_plan=payload.audience_plan, starts_at=payload.starts_at,
        ends_at=payload.ends_at)
    service.audit.record(admin=admin, action="broadcast.create",
                         resource=f"broadcast:{b.broadcast_id}", ip_address=ip,
                         new_value={"title": b.title, "audience": b.audience.value})
    return {"broadcast_id": b.broadcast_id, "title": b.title, "active": b.active}


@router.delete("/broadcasts/{broadcast_id}", response_model=dict,
               summary="Deactivate a broadcast (Super Admin)")
def deactivate_broadcast(broadcast_id: str, ip: str | None = Depends(client_ip),
                         admin: PanelAdmin = Depends(get_panel_admin),
                         service=Depends(get_panel_service), db=Depends(get_db)) -> dict:
    require(admin.role, Capability.SYSTEM_SETTINGS)
    b = container.broadcast_service(db).deactivate(broadcast_id)
    service.audit.record(admin=admin, action="broadcast.deactivate",
                         resource=f"broadcast:{broadcast_id}", ip_address=ip,
                         new_value={"active": False})
    return {"broadcast_id": broadcast_id, "active": bool(b and b.active)}


# --- usage dashboard --------------------------------------------------------

@router.get("/usage", response_model=dict, summary="System-wide usage and estimated cost")
def system_usage(days: int = Query(default=30, ge=1, le=90),
                 admin: PanelAdmin = Depends(get_panel_admin), db=Depends(get_db)) -> dict:
    require(admin.role, Capability.VIEW_USERS)
    from app.admin.usage_metrics import UsageMetricsService, cost_per_1k
    svc = UsageMetricsService(db)
    s = svc.summary()
    return {
        "summary": {
            "tokens_today": s.tokens_today,
            "tokens_month": s.tokens_month,
            "requests_month": s.requests_month,
            "avg_tokens_per_request": s.avg_tokens_per_request,
            # Labelled "estimated" everywhere: it is tokens x a blended rate, not a
            # provider invoice, and must never be reconciled against a real bill.
            "estimated_cost_today_usd": s.estimated_cost_today_usd,
            "estimated_cost_month_usd": s.estimated_cost_month_usd,
            "cost_basis_per_1k_usd": cost_per_1k(),
            "unbilled_tokens": s.unbilled_tokens,
            "unbilled_credits": s.unbilled_credits,
        },
        "daily": svc.daily_series(days=days),
        "top_consumers": svc.top_consumers(limit=10),
    }


@router.get("/users/{founder_id}/usage", response_model=dict,
            summary="One founder's usage and remaining credits")
def founder_usage(founder_id: int, days: int = Query(default=30, ge=1, le=90),
                  admin: PanelAdmin = Depends(get_panel_admin), db=Depends(get_db)) -> dict:
    require(admin.role, Capability.VIEW_USERS)
    from app.admin.usage_metrics import UsageMetricsService
    svc = UsageMetricsService(db)
    s = svc.summary(founder_id)
    return {
        "founder_id": founder_id,
        "tokens_today": s.tokens_today,
        "tokens_month": s.tokens_month,
        "requests_month": s.requests_month,
        "avg_tokens_per_request": s.avg_tokens_per_request,
        "credits_remaining": s.credits_remaining,
        "estimated_cost_today_usd": s.estimated_cost_today_usd,
        "estimated_cost_month_usd": s.estimated_cost_month_usd,
        "unbilled_tokens": s.unbilled_tokens,
        "daily": svc.daily_series(founder_id, days=days),
    }


@router.post("/usage/reconcile", response_model=dict,
             summary="Replay unbilled usage against the ledger (Super Admin)")
def reconcile_usage(admin: PanelAdmin = Depends(get_panel_admin),
                    service=Depends(get_panel_service), db=Depends(get_db)) -> dict:
    require(admin.role, Capability.TRANSFER_CREDITS)
    from app.plans.reconciliation import (
        ReconciliationService,
        SqlAlchemyReconciliationRepository,
    )
    recon = ReconciliationService(SqlAlchemyReconciliationRepository(db),
                                  credit_service=container.credit_service(db))
    before = recon.pending()
    result = recon.replay()
    service.audit.record(admin=admin, action="usage.reconcile", resource="unbilled_usage",
                         old_value=before, new_value=result)
    return {"before": before, "result": result, "after": recon.pending()}


# --- coupons ----------------------------------------------------------------
#
# Creating a coupon decides what founders pay, so it sits behind
# MODIFY_SUBSCRIPTION -- the same capability that already gates changing a
# founder's plan by hand, and Super Admin only. Reading the list is VIEW_USERS,
# because "how many of the first 100 are left" is a question support gets asked
# and can answer without being able to mint discounts.
#
# There is no DELETE. A redeemed coupon is a financial record: deactivating it
# stops further use and keeps the history that explains a discounted payment.

_MAX_BULK_CODES = 200


class CouponCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=3, max_length=40)
    description: str | None = Field(default=None, max_length=500)
    discount_type: str = Field(pattern="^(percent|fixed)$")
    discount_value: int = Field(ge=1)
    applies_to: list[str] | None = None
    max_redemptions: int | None = Field(default=None, ge=1)
    max_per_founder: int = Field(default=1, ge=1)
    valid_from: datetime | None = None
    # Required, with no default. Every coupon expires at a moment somebody
    # chose; a discount with no end date is one nobody remembers to switch off.
    valid_until: datetime


class CouponUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str | None = Field(default=None, max_length=500)
    max_redemptions: int | None = Field(default=None, ge=1)
    max_per_founder: int | None = Field(default=None, ge=1)
    valid_until: datetime | None = None
    is_active: bool | None = None


class CouponBulkRequest(BaseModel):
    """Generate N unique single-use codes under a shared prefix -- the shape you
    want for partners or influencers, where each recipient gets their own code.
    The "first 100 customers" case is the opposite shape: ONE code with
    max_redemptions=100, created through the endpoint above."""

    model_config = ConfigDict(extra="forbid")

    prefix: str = Field(min_length=2, max_length=20)
    count: int = Field(ge=1, le=_MAX_BULK_CODES)
    discount_type: str = Field(pattern="^(percent|fixed)$")
    discount_value: int = Field(ge=1)
    applies_to: list[str] | None = None
    valid_until: datetime
    description: str | None = Field(default=None, max_length=500)


def _coupon_repo(db: Session):
    from app.coupons.repository import CouponRepository
    return CouponRepository(db)


@router.get("/coupons", response_model=dict, summary="List coupons with usage")
def list_coupons(include_inactive: bool = Query(default=True),
                 limit: int = Query(default=100, ge=1, le=500),
                 offset: int = Query(default=0, ge=0),
                 admin: PanelAdmin = Depends(get_panel_admin),
                 db: Session = Depends(get_db)) -> dict:
    require(admin.role, Capability.VIEW_USERS)
    rows = _coupon_repo(db).list_with_usage(
        include_inactive=include_inactive, limit=limit, offset=offset)
    return {"coupons": [_coupon_row(r) for r in rows]}


@router.post("/coupons", response_model=dict, status_code=201,
             summary="Create a coupon (Super Admin only)")
def create_coupon(payload: CouponCreateRequest,
                  admin: PanelAdmin = Depends(get_panel_admin),
                  db: Session = Depends(get_db)) -> dict:
    require(admin.role, Capability.MODIFY_SUBSCRIPTION)
    from app.coupons.service import normalise

    _validate_discount(payload.discount_type, payload.discount_value)
    _validate_tiers(payload.applies_to)
    code = normalise(payload.code)
    repo = _coupon_repo(db)
    if repo.get_by_code(code) is not None:
        raise AppError(f"A coupon with the code {code} already exists.", status_code=409)

    coupon_id = repo.create(
        code=code, description=payload.description, discount_type=payload.discount_type,
        discount_value=payload.discount_value, applies_to=payload.applies_to,
        max_redemptions=payload.max_redemptions, max_per_founder=payload.max_per_founder,
        valid_from=payload.valid_from, valid_until=payload.valid_until,
        admin_id=admin.admin_id)
    logger.info("admin: coupon created", extra={"admin_id": admin.admin_id, "code": code,
                                                "coupon_id": coupon_id})
    return {"coupon_id": coupon_id, "code": code}


@router.post("/coupons/bulk", response_model=dict, status_code=201,
             summary="Generate unique single-use codes (Super Admin only)")
def bulk_coupons(payload: CouponBulkRequest,
                 admin: PanelAdmin = Depends(get_panel_admin),
                 db: Session = Depends(get_db)) -> dict:
    require(admin.role, Capability.MODIFY_SUBSCRIPTION)
    import secrets

    from app.coupons.service import normalise

    _validate_discount(payload.discount_type, payload.discount_value)
    _validate_tiers(payload.applies_to)
    repo = _coupon_repo(db)
    prefix = normalise(payload.prefix)

    # Unambiguous alphabet: no O/0, no I/1. These get read aloud and copied off
    # screenshots, and a code nobody can transcribe is a support ticket.
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    created: list[str] = []
    for _ in range(payload.count):
        for _attempt in range(5):
            code = f"{prefix}-{''.join(secrets.choice(alphabet) for _ in range(6))}"
            if repo.get_by_code(code) is None:
                repo.create(code=code, description=payload.description,
                            discount_type=payload.discount_type,
                            discount_value=payload.discount_value,
                            applies_to=payload.applies_to, max_redemptions=1,
                            max_per_founder=1, valid_from=None,
                            valid_until=payload.valid_until, admin_id=admin.admin_id)
                created.append(code)
                break
    logger.info("admin: coupons generated", extra={"admin_id": admin.admin_id,
                                                   "count": len(created), "prefix": prefix})
    return {"created": len(created), "codes": created}


@router.patch("/coupons/{coupon_id}", response_model=dict,
              summary="Deactivate, extend or re-cap a coupon (Super Admin only)")
def update_coupon(coupon_id: int, payload: CouponUpdateRequest,
                  admin: PanelAdmin = Depends(get_panel_admin),
                  db: Session = Depends(get_db)) -> dict:
    require(admin.role, Capability.MODIFY_SUBSCRIPTION)
    repo = _coupon_repo(db)
    if repo.get_by_id(coupon_id) is None:
        raise AppError(f"No coupon with id {coupon_id}.", status_code=404)
    changed = repo.update(coupon_id, **payload.model_dump(exclude_none=True))
    logger.info("admin: coupon updated", extra={"admin_id": admin.admin_id,
                                                "coupon_id": coupon_id, "changed": changed})
    return {"coupon_id": coupon_id, "updated": changed}


@router.get("/coupons/{coupon_id}/redemptions", response_model=dict,
            summary="Who redeemed a coupon and when")
def coupon_redemptions(coupon_id: int, limit: int = Query(default=200, ge=1, le=1000),
                       admin: PanelAdmin = Depends(get_panel_admin),
                       db: Session = Depends(get_db)) -> dict:
    require(admin.role, Capability.VIEW_USERS)
    repo = _coupon_repo(db)
    if repo.get_by_id(coupon_id) is None:
        raise AppError(f"No coupon with id {coupon_id}.", status_code=404)
    rows = repo.redemptions_for(coupon_id, limit=limit)
    return {"redemptions": [
        {"redemption_id": r["redemption_id"], "founder_id": r["founder_id"],
         "email": r["email"], "full_name": r["full_name"], "payment_id": r["payment_id"],
         "status": r["status"], "discount_inr": int(r["discount_inr"]),
         "created_at": r["created_at"].isoformat() if r["created_at"] else None,
         "confirmed_at": r["confirmed_at"].isoformat() if r["confirmed_at"] else None}
        for r in rows]}


def _validate_discount(discount_type: str, value: int) -> None:
    """99, not 100. Razorpay cannot create an order for zero, so a free coupon
    would need a second, gateway-free grant path; one path is worth more than
    the feature. The database CHECK enforces the same bound -- this exists to
    give the admin a sentence instead of a constraint violation."""
    if discount_type == "percent" and not 1 <= value <= 99:
        raise AppError("A percentage discount must be between 1 and 99. "
                       "A 100% coupon can't be charged through Razorpay.",
                       status_code=422)


def _validate_tiers(applies_to: list[str] | None) -> None:
    if not applies_to:
        return
    from app.plans.catalog import PLANS, PlanTier
    for value in applies_to:
        try:
            tier = PlanTier(value)
        except ValueError:
            raise AppError(f"Unknown plan tier {value!r}.", status_code=422) from None
        if not PLANS[tier].is_paid:
            raise AppError(f"{PLANS[tier].name} is free -- a coupon cannot apply to it.",
                           status_code=422)


def _coupon_row(r: dict) -> dict:
    confirmed = int(r["confirmed_count"] or 0)
    pending = int(r["pending_count"] or 0)
    cap = r["max_redemptions"]
    return {
        "coupon_id": r["coupon_id"], "code": r["code"], "description": r["description"],
        "discount_type": r["discount_type"], "discount_value": int(r["discount_value"]),
        "applies_to": list(r["applies_to"]) if r["applies_to"] else None,
        "max_redemptions": cap, "max_per_founder": int(r["max_per_founder"]),
        "valid_from": r["valid_from"].isoformat() if r["valid_from"] else None,
        "valid_until": r["valid_until"].isoformat() if r["valid_until"] else None,
        "is_active": bool(r["is_active"]),
        "confirmed_count": confirmed,
        # In-flight checkouts. Shown separately so "3 of 100 used" and "and 2
        # people are paying right now" are not the same number.
        "pending_count": pending,
        "remaining": None if cap is None else max(0, cap - confirmed - pending),
        "discount_given_inr": int(r["discount_given_inr"] or 0),
    }
