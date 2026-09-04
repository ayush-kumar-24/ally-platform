"""Admin Panel: the growth layer -- coupons, discounts and beta access.

    Coupons (Super Admin to write, Admin+ to read)
    GET    /admin/coupons                       list
    POST   /admin/coupons                       create
    PATCH  /admin/coupons/{code}                retire / extend / re-cap
    GET    /admin/coupons/{code}/redemptions    who has claimed it

    Beta access
    GET    /admin/beta/waitlist                 the list, in queue order
    GET    /admin/beta/waitlist/stats           counts by status
    GET    /admin/beta/waitlist/next-up         who the next release would take
    POST   /admin/beta/waitlist                 add one founder by email
    POST   /admin/beta/waitlist/import          paste a batch of emails
    PATCH  /admin/beta/waitlist/{entry_id}      priority / status
    GET    /admin/beta/cohorts                  list
    POST   /admin/beta/cohorts                  open a slot
    GET    /admin/beta/cohorts/{id}             one slot + its members
    POST   /admin/beta/cohorts/{id}/select      stage the picks (sends nothing)
    POST   /admin/beta/cohorts/{id}/release     invite, defer the rest, queue mail
    POST   /admin/beta/entries/{id}/resend      re-queue one invite
    POST   /admin/beta/dispatch                 drain the mail queue / retry failures

Select and release are separate endpoints, not one flag, because they have
different blast radii: selection is reviewable and reversible, release mails every
founder on the list. The UI can present them as two steps because they are two.

`release` returns as soon as the database is consistent and hands the mail to a
background task. That is why `POST /admin/beta/dispatch` exists as its own route:
if the process dies mid-batch the queue is still on disk, and draining it again is
safe -- only queued and failed rows are picked up.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from pydantic import BaseModel, ConfigDict, Field

from app.admin.beta import EntryStatus, InvalidCohortError
from app.admin.coupons import DiscountType, describe_discount
from app.admin.rbac import Capability, require
from app.api.v1.admin.panel_dependencies import PanelAdmin, client_ip, get_panel_admin
from app.api.v1.admin.panel_router import ConfirmationRequiredError
from app.core.container import container
from app.db.session import get_db

router = APIRouter(prefix="/admin", tags=["admin-growth"])


# --- schemas ----------------------------------------------------------------

class CouponCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=3, max_length=40)
    discount_type: DiscountType
    #: Percent 1-100, fixed in paise, credits as a count, free_days as days.
    #: The service range-checks per type -- this bound only stops absurd input.
    discount_value: int = Field(ge=1, le=10_000_000)
    description: str = Field(default="", max_length=300)
    applies_to_plans: list[str] = Field(default_factory=list, max_length=10)
    max_redemptions: int | None = Field(default=None, ge=1, le=1_000_000)
    max_per_founder: int = Field(default=1, ge=1, le=100)
    starts_at: datetime | None = None
    expires_at: datetime | None = None


class CouponPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active: bool | None = None
    description: str | None = Field(default=None, max_length=300)
    max_redemptions: int | None = Field(default=None, ge=1, le=1_000_000)
    clear_max_redemptions: bool = False
    expires_at: datetime | None = None
    clear_expires_at: bool = False


class WaitlistAddRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=200)
    full_name: str = Field(default="", max_length=120)


class WaitlistImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: One address per line, or comma-separated -- whatever the admin pasted.
    emails: str = Field(min_length=3, max_length=100_000)


class EntryPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    priority: int | None = Field(default=None, ge=-1000, le=1000)
    status: EntryStatus | None = None


class CohortCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    slot_size: int = Field(ge=1, le=5000)
    coupon_code: str | None = Field(default=None, max_length=40)
    notify_deferred: bool = True


class SelectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: Exactly one of these. entry_ids is the checkbox selection; auto_count takes
    #: the top N straight off the queue.
    entry_ids: list[str] | None = Field(default=None, max_length=5000)
    auto_count: int | None = Field(default=None, ge=1, le=5000)


class ConfirmRelease(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: Explicit, because this is the button that sends the mail.
    confirm: bool = False


# --- serialisers ------------------------------------------------------------

def _coupon_json(c) -> dict:
    return {
        "code": c.code,
        "description": c.description,
        "discount_type": c.discount_type.value,
        "discount_value": c.discount_value,
        "discount_label": describe_discount(c.discount_type, c.discount_value),
        "applies_to_plans": c.applies_to_plans,
        "max_redemptions": c.max_redemptions,
        "max_per_founder": c.max_per_founder,
        "redeemed_count": c.redeemed_count,
        "remaining": (None if c.max_redemptions is None
                      else max(0, c.max_redemptions - c.redeemed_count)),
        "starts_at": c.starts_at,
        "expires_at": c.expires_at,
        "active": c.active,
        "created_by": c.created_by,
        "created_at": c.created_at,
    }


def _entry_json(e) -> dict:
    return {
        "entry_id": e.entry_id,
        "email": e.email,
        "full_name": e.full_name,
        "founder_id": e.founder_id,
        "status": e.status.value,
        "source": e.source,
        "times_deferred": e.times_deferred,
        "priority": e.priority,
        "cohort_id": e.cohort_id,
        "joined_at": e.joined_at,
        "invited_at": e.invited_at,
        "responded_at": e.responded_at,
        "coupon_code": e.coupon_code,
        "email_kind": e.email_kind.value if e.email_kind else None,
        "email_state": e.email_state.value,
        "email_error": e.email_error,
        "email_sent_at": e.email_sent_at,
    }


def _cohort_json(c) -> dict:
    return {
        "cohort_id": c.cohort_id,
        "name": c.name,
        "slot_size": c.slot_size,
        "status": c.status.value,
        "coupon_code": c.coupon_code,
        "notify_deferred": c.notify_deferred,
        "created_by": c.created_by,
        "created_at": c.created_at,
        "released_at": c.released_at,
        "invited_count": c.invited_count,
        "deferred_count": c.deferred_count,
    }


# --- coupons ----------------------------------------------------------------

@router.get("/coupons", response_model=dict, summary="List coupons")
def list_coupons(include_inactive: bool = Query(default=True),
                 limit: int = Query(default=100, ge=1, le=500),
                 offset: int = Query(default=0, ge=0),
                 admin: PanelAdmin = Depends(get_panel_admin), db=Depends(get_db)) -> dict:
    require(admin.role, Capability.VIEW_GROWTH)
    items, total = container.coupon_service(db).list(
        include_inactive=include_inactive, limit=limit, offset=offset)
    return {"total": total, "items": [_coupon_json(c) for c in items]}


@router.post("/coupons", response_model=dict, status_code=201,
             summary="Create a coupon (Super Admin only)")
def create_coupon(payload: CouponCreateRequest, ip: str | None = Depends(client_ip),
                  admin: PanelAdmin = Depends(get_panel_admin), db=Depends(get_db)) -> dict:
    require(admin.role, Capability.MANAGE_COUPONS)
    coupon = container.coupon_service(db).create(
        code=payload.code, discount_type=payload.discount_type,
        discount_value=payload.discount_value, description=payload.description,
        applies_to_plans=payload.applies_to_plans, max_redemptions=payload.max_redemptions,
        max_per_founder=payload.max_per_founder, starts_at=payload.starts_at,
        expires_at=payload.expires_at, admin_id=admin.admin_id)
    _audit(db, admin, action="coupon.create", resource=f"coupon:{coupon.code}",
           new_value=_coupon_json(coupon), ip=ip)
    return _coupon_json(coupon)


@router.patch("/coupons/{code}", response_model=dict,
              summary="Retire, extend or re-cap a coupon (Super Admin only)")
def patch_coupon(code: str, payload: CouponPatchRequest, ip: str | None = Depends(client_ip),
                 admin: PanelAdmin = Depends(get_panel_admin), db=Depends(get_db)) -> dict:
    require(admin.role, Capability.MANAGE_COUPONS)
    service = container.coupon_service(db)
    before = service.get(code)
    coupon = service.update(
        code, active=payload.active, description=payload.description,
        max_redemptions=payload.max_redemptions,
        clear_max_redemptions=payload.clear_max_redemptions,
        expires_at=payload.expires_at, clear_expires_at=payload.clear_expires_at)
    _audit(db, admin, action="coupon.update", resource=f"coupon:{coupon.code}",
           old_value=_coupon_json(before) if before else None,
           new_value=_coupon_json(coupon), ip=ip)
    return _coupon_json(coupon)


@router.get("/coupons/{code}/redemptions", response_model=dict,
            summary="Who has claimed this coupon")
def coupon_redemptions(code: str, limit: int = Query(default=100, ge=1, le=500),
                       offset: int = Query(default=0, ge=0),
                       admin: PanelAdmin = Depends(get_panel_admin),
                       db=Depends(get_db)) -> dict:
    require(admin.role, Capability.VIEW_GROWTH)
    items, total = container.coupon_service(db).list_redemptions(
        code, limit=limit, offset=offset)
    return {"code": code.upper(), "total": total, "items": [
        {"redemption_id": r.redemption_id, "founder_id": r.founder_id,
         "context": r.context, "redeemed_at": r.redeemed_at} for r in items]}


# --- beta waitlist ----------------------------------------------------------

@router.get("/beta/waitlist", response_model=dict,
            summary="The waitlist, most-deferred first")
def list_waitlist(status: EntryStatus | None = Query(default=None),
                  search: str | None = Query(default=None, max_length=200),
                  cohort_id: str | None = Query(default=None, max_length=64),
                  limit: int = Query(default=100, ge=1, le=500),
                  offset: int = Query(default=0, ge=0),
                  admin: PanelAdmin = Depends(get_panel_admin), db=Depends(get_db)) -> dict:
    require(admin.role, Capability.VIEW_GROWTH)
    items, total = container.beta_service(db).list_entries(
        status=status, search=search, cohort_id=cohort_id, limit=limit, offset=offset)
    return {"total": total, "items": [_entry_json(e) for e in items]}


@router.get("/beta/waitlist/stats", response_model=dict, summary="Counts by status")
def waitlist_stats(admin: PanelAdmin = Depends(get_panel_admin), db=Depends(get_db)) -> dict:
    require(admin.role, Capability.VIEW_GROWTH)
    service = container.beta_service(db)
    return {"counts": service.stats(), "pending_emails": service.pending_email_count()}


@router.get("/beta/waitlist/next-up", response_model=dict,
            summary="Who the next release would take, in order")
def next_up(limit: int = Query(default=100, ge=1, le=1000),
            admin: PanelAdmin = Depends(get_panel_admin), db=Depends(get_db)) -> dict:
    require(admin.role, Capability.VIEW_GROWTH)
    entries = container.beta_service(db).next_up(limit)
    return {"total": len(entries), "items": [_entry_json(e) for e in entries]}


@router.post("/beta/waitlist", response_model=dict, status_code=201,
             summary="Add one founder to the waitlist")
def add_to_waitlist(payload: WaitlistAddRequest, ip: str | None = Depends(client_ip),
                    admin: PanelAdmin = Depends(get_panel_admin), db=Depends(get_db)) -> dict:
    require(admin.role, Capability.MANAGE_BETA_ACCESS)
    entry, created = container.beta_service(db).join(
        email=payload.email, full_name=payload.full_name, source="admin")
    if created:
        _audit(db, admin, action="beta.waitlist.add", resource=f"beta_entry:{entry.entry_id}",
               new_value={"email": entry.email}, ip=ip)
    return {"created": created, "entry": _entry_json(entry)}


@router.post("/beta/waitlist/import", response_model=dict,
             summary="Add a pasted batch of emails to the waitlist")
def import_waitlist(payload: WaitlistImportRequest, ip: str | None = Depends(client_ip),
                    admin: PanelAdmin = Depends(get_panel_admin), db=Depends(get_db)) -> dict:
    """Deliberately tolerant of what an admin actually pastes: newlines, commas,
    semicolons, blank lines and duplicates all get normalised. Addresses that don't
    parse are returned as `rejected` rather than silently dropped -- a batch that
    quietly imported 97 of 100 is how people end up short and never find out."""
    require(admin.role, Capability.MANAGE_BETA_ACCESS)
    service = container.beta_service(db)

    raw = payload.emails.replace(",", "\n").replace(";", "\n").split("\n")
    added = skipped = 0
    rejected: list[str] = []
    for token in raw:
        candidate = token.strip()
        if not candidate:
            continue
        try:
            _, created = service.join(email=candidate, source="import")
        except Exception:
            rejected.append(candidate[:100])
            continue
        added += created
        skipped += (not created)

    _audit(db, admin, action="beta.waitlist.import", resource="beta_waitlist",
           new_value={"added": added, "already_present": skipped,
                      "rejected": len(rejected)}, ip=ip)
    return {"added": added, "already_present": skipped, "rejected": rejected}


@router.patch("/beta/waitlist/{entry_id}", response_model=dict,
              summary="Bump priority or set the status of one entry")
def patch_entry(entry_id: str, payload: EntryPatchRequest, ip: str | None = Depends(client_ip),
                admin: PanelAdmin = Depends(get_panel_admin), db=Depends(get_db)) -> dict:
    require(admin.role, Capability.MANAGE_BETA_ACCESS)
    if payload.priority is None and payload.status is None:
        # An empty PATCH is a caller bug, not a no-op to absorb: absorbing it
        # would write an audit record for a change that never happened.
        raise InvalidCohortError("send priority, status, or both")

    service = container.beta_service(db)
    entry = None
    if payload.priority is not None:
        entry = service.set_priority(entry_id, payload.priority)
    if payload.status is not None:
        entry = service.set_status(entry_id, payload.status)
    _audit(db, admin, action="beta.entry.update", resource=f"beta_entry:{entry.entry_id}",
           target_user_id=entry.founder_id, new_value=_entry_json(entry), ip=ip)
    return _entry_json(entry)


# --- cohorts ----------------------------------------------------------------

@router.get("/beta/cohorts", response_model=dict, summary="List beta cohorts")
def list_cohorts(limit: int = Query(default=50, ge=1, le=200),
                 offset: int = Query(default=0, ge=0),
                 admin: PanelAdmin = Depends(get_panel_admin), db=Depends(get_db)) -> dict:
    require(admin.role, Capability.VIEW_GROWTH)
    items, total = container.beta_service(db).list_cohorts(limit=limit, offset=offset)
    return {"total": total, "items": [_cohort_json(c) for c in items]}


@router.post("/beta/cohorts", response_model=dict, status_code=201,
             summary="Open a new slot (Super Admin only)")
def create_cohort(payload: CohortCreateRequest, ip: str | None = Depends(client_ip),
                  admin: PanelAdmin = Depends(get_panel_admin), db=Depends(get_db)) -> dict:
    require(admin.role, Capability.MANAGE_BETA_ACCESS)
    cohort = container.beta_service(db).create_cohort(
        name=payload.name, slot_size=payload.slot_size, coupon_code=payload.coupon_code,
        notify_deferred=payload.notify_deferred, admin_id=admin.admin_id)
    _audit(db, admin, action="beta.cohort.create", resource=f"beta_cohort:{cohort.cohort_id}",
           new_value=_cohort_json(cohort), ip=ip)
    return _cohort_json(cohort)


@router.get("/beta/cohorts/{cohort_id}", response_model=dict,
            summary="One cohort and its members")
def get_cohort(cohort_id: str, admin: PanelAdmin = Depends(get_panel_admin),
               db=Depends(get_db)) -> dict:
    require(admin.role, Capability.VIEW_GROWTH)
    service = container.beta_service(db)
    cohort = service.get_cohort(cohort_id)
    members, total = service.list_entries(cohort_id=cohort_id, limit=500)
    return {"cohort": _cohort_json(cohort), "member_count": total,
            "members": [_entry_json(e) for e in members]}


@router.post("/beta/cohorts/{cohort_id}/select", response_model=dict,
             summary="Stage the picks into an open cohort (sends nothing)")
def select_into_cohort(cohort_id: str, payload: SelectRequest,
                       ip: str | None = Depends(client_ip),
                       admin: PanelAdmin = Depends(get_panel_admin),
                       db=Depends(get_db)) -> dict:
    require(admin.role, Capability.MANAGE_BETA_ACCESS)
    selected = container.beta_service(db).select(
        cohort_id, entry_ids=payload.entry_ids, auto_count=payload.auto_count)
    _audit(db, admin, action="beta.cohort.select", resource=f"beta_cohort:{cohort_id}",
           new_value={"selected": len(selected),
                      "emails": [e.email for e in selected[:50]]}, ip=ip)
    return {"selected": len(selected), "items": [_entry_json(e) for e in selected]}


@router.post("/beta/cohorts/{cohort_id}/release", response_model=dict,
             summary="Invite the selected, defer the rest, queue the mail")
def release_cohort(cohort_id: str, payload: ConfirmRelease, background: BackgroundTasks,
                   ip: str | None = Depends(client_ip),
                   admin: PanelAdmin = Depends(get_panel_admin), db=Depends(get_db)) -> dict:
    require(admin.role, Capability.MANAGE_BETA_ACCESS)
    if not payload.confirm:
        raise ConfirmationRequiredError("release")

    result = container.beta_service(db).release(cohort_id)
    _audit(db, admin, action="beta.cohort.release",
           resource=f"beta_cohort:{cohort_id}",
           new_value={"invited": result.invited, "deferred": result.deferred,
                      "queued_emails": result.queued_emails}, ip=ip)
    # The state change is committed; mail is a separate, resumable job.
    background.add_task(_drain_queue, result.queued_emails)
    return {"cohort": _cohort_json(result.cohort), "invited": result.invited,
            "deferred": result.deferred, "queued_emails": result.queued_emails}


@router.post("/beta/entries/{entry_id}/resend", response_model=dict,
             summary="Re-queue one invite email")
def resend_invite(entry_id: str, background: BackgroundTasks,
                  ip: str | None = Depends(client_ip),
                  admin: PanelAdmin = Depends(get_panel_admin), db=Depends(get_db)) -> dict:
    require(admin.role, Capability.MANAGE_BETA_ACCESS)
    entry = container.beta_service(db).queue_invite(entry_id)
    _audit(db, admin, action="beta.invite.resend", resource=f"beta_entry:{entry_id}",
           target_user_id=entry.founder_id, new_value={"email": entry.email}, ip=ip)
    background.add_task(_drain_queue, 1)
    return _entry_json(entry)


@router.post("/beta/dispatch", response_model=dict,
             summary="Drain the mail queue and retry failures")
def dispatch(limit: int = Query(default=200, ge=1, le=2000),
             admin: PanelAdmin = Depends(get_panel_admin), db=Depends(get_db)) -> dict:
    """Idempotent by construction -- only queued and failed rows are picked up, so
    running it twice cannot double-send. This is the manual half of what `release`
    kicks off in the background, and the recovery path when that background task
    did not survive a restart."""
    require(admin.role, Capability.MANAGE_BETA_ACCESS)
    result = container.beta_service(db).dispatch_pending(limit=limit)
    return {"sent": result.sent, "failed": result.failed, "skipped": result.skipped,
            "failures": result.failures}


# --- helpers ----------------------------------------------------------------

def _drain_queue(expected: int) -> None:
    """Background mail drain. Opens its OWN session: the request's session is
    closed by the time a BackgroundTask runs, so reusing it would raise on the
    first query."""
    from app.core.logger import logger
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        result = container.beta_service(db).dispatch_pending(limit=max(1, expected))
        logger.info("Beta mail dispatched",
                    extra={"path": f"sent={result.sent} failed={result.failed} "
                                   f"skipped={result.skipped}"})
    except Exception:
        # The queue is durable; a failed drain is retried by POST /admin/beta/dispatch.
        logger.warning("Beta mail dispatch failed", extra={"path": "beta.dispatch"})
    finally:
        db.close()


def _audit(db, admin: PanelAdmin, *, action: str, resource: str,
           target_user_id: int | None = None, old_value=None, new_value=None,
           ip: str | None = None) -> None:
    from app.admin.panel_audit import AuditRecorder, SqlAlchemyPanelAuditRepository
    AuditRecorder(SqlAlchemyPanelAuditRepository(db)).record(
        admin=admin, action=action, resource=resource, target_user_id=target_user_id,
        old_value=old_value, new_value=new_value, ip_address=ip)
