"""Team-side handling of waitlist registrations -- the screen where access is
actually granted.

    GET  /admin/waitlist                the queue, oldest request first
    POST /admin/waitlist/{id}/approve   create their login and email them
    POST /admin/waitlist/{id}/reject    turn it down, with a reason
    GET  /admin/waitlist/slots/preview  who the next N slots would let in
    POST /admin/waitlist/slots/open     open N slots, approve those N

Two different tiers on purpose. Reading the queue is VIEW_USERS, the same tier
as seeing users, so Support can answer "did my registration arrive?" without
being able to let anyone in. Answering it is MANAGE_WAITLIST, which Support
does not hold.

Oldest first, not newest: this is a queue of people waiting, and the person who
has waited longest should be the one you see. The Calls screen sorts the other
way because a call request is about an upcoming date; this is about a backlog.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.admin.rbac import Capability, require
from app.api.v1.admin.panel_dependencies import PanelAdmin, get_panel_admin
from app.db.session import get_db
from app.models.waitlist import PENDING, STATUSES, WaitlistRegistration
from app.services import supabase_admin
from app.services.waitlist import (
    approve,
    cap_status,
    next_in_queue,
    open_slots,
    reject,
)

router = APIRouter(prefix="/admin/waitlist", tags=["admin"])


class RegistrationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    registration_id: int
    email: str
    full_name: str
    company: str | None
    role_title: str | None
    stage: str | None
    note: str | None
    source: str | None
    status: str
    created_at: datetime
    decided_at: datetime | None
    decided_by_email: str | None
    decision_reason: str | None
    access_granted_at: datetime | None
    approval_email_sent_at: datetime | None
    #: Approved AND holding an identity. Shown instead of a bare status because
    #: "approved" alone does not mean the founder can log in -- see the model.
    can_sign_in: bool


class CapOut(BaseModel):
    approved: int
    cap: int
    #: Where the cap came from: the environment's starting size, plus every
    #: slot opened from the panel since. Shown apart so the number reads as a
    #: decision somebody made rather than a constant.
    base_cap: int
    slots_opened: int
    remaining: int
    is_full: bool
    #: Whether approving can create a login at all right now. False means
    #: SUPABASE_SERVICE_ROLE_KEY is unset, and the panel says so up front
    #: rather than letting someone click approve into a 503.
    can_grant_access: bool


class QueueOut(BaseModel):
    registrations: list[RegistrationOut]
    counts: dict[str, int]
    cap: CapOut


class RejectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    #: Recorded, never emailed -- see services/waitlist.reject for why nobody
    #: is sent a rejection notice. Required, because "rejected, no reason" is
    #: not something anyone can act on three months later.
    reason: str = Field(min_length=1, max_length=500)


@router.get("", response_model=QueueOut)
def list_registrations(
    status_filter: str | None = Query(default="pending", alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    admin: PanelAdmin = Depends(get_panel_admin),
    db: Session = Depends(get_db),
):
    """The queue. Defaults to pending, which is the only view with work in it."""
    require(admin.role, Capability.VIEW_USERS)

    stmt = select(WaitlistRegistration)
    if status_filter and status_filter != "all":
        # Validated against the model's own tuple rather than trusted: an
        # unknown value would otherwise return an empty list that looks like an
        # empty queue.
        if status_filter not in STATUSES:
            status_filter = "pending"
        stmt = stmt.where(WaitlistRegistration.status == status_filter)

    rows = (
        db.execute(
            stmt.order_by(WaitlistRegistration.created_at.asc()).limit(limit).offset(offset)
        )
        .scalars()
        .all()
    )

    counts = {s: 0 for s in STATUSES}
    for status_value, count in db.execute(
        select(WaitlistRegistration.status, func.count())
        .group_by(WaitlistRegistration.status)
    ).all():
        counts[status_value] = int(count)

    return QueueOut(
        registrations=[RegistrationOut.model_validate(r) for r in rows],
        counts=counts,
        cap=CapOut(**cap_status(db), can_grant_access=supabase_admin.is_configured()),
    )


@router.post("/{registration_id}/approve", response_model=RegistrationOut)
def approve_registration(
    registration_id: int,
    admin: PanelAdmin = Depends(get_panel_admin),
    db: Session = Depends(get_db),
):
    """Create the founder's login, mark the registration, and email them.

    Refuses at the cap unless the caller is a super admin. The role is passed
    down rather than checked here because the cap is not a separate permission
    -- it is the same approval at a different limit.
    """
    require(admin.role, Capability.MANAGE_WAITLIST)
    row = approve(
        db,
        registration_id,
        admin_id=admin.admin_id,
        admin_email=admin.email,
        admin_role=admin.role,
    )
    return RegistrationOut.model_validate(row)


@router.post("/{registration_id}/reject", response_model=RegistrationOut)
def reject_registration(
    registration_id: int,
    payload: RejectRequest,
    admin: PanelAdmin = Depends(get_panel_admin),
    db: Session = Depends(get_db),
):
    """Turn a registration down. No email is sent -- see services/waitlist."""
    require(admin.role, Capability.MANAGE_WAITLIST)
    row = reject(
        db,
        registration_id,
        reason=payload.reason,
        admin_id=admin.admin_id,
        admin_email=admin.email,
    )
    return RegistrationOut.model_validate(row)


class OpenSlotsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: Upper bound is a guard against a typed zero, not a policy: 500 logins
    #: and 500 emails from one click is already far past anything the team
    #: means to do in one sitting.
    slots: int = Field(ge=1, le=500)


class SlotFailureOut(BaseModel):
    email: str
    full_name: str
    #: The API's own message for why this one did not go through, passed
    #: straight to the panel: "already approved" and "identity provider is not
    #: configured" need different answers from a human.
    reason: str


class SlotPreviewOut(BaseModel):
    slots: int
    #: Exactly who would be let in, in the order they would be -- the same
    #: order the queue is displayed in.
    would_approve: list[RegistrationOut]
    pending_total: int
    #: Slots that would go unused because the queue is shorter than the number
    #: asked for. They stay available for whoever registers next.
    unused_slots: int
    cap: CapOut


class SlotsOpenedOut(BaseModel):
    slots: int
    approved: list[RegistrationOut]
    failures: list[SlotFailureOut]
    cap: CapOut


@router.get("/slots/preview", response_model=SlotPreviewOut)
def preview_slots(
    slots: int = Query(ge=1, le=500),
    admin: PanelAdmin = Depends(get_panel_admin),
    db: Session = Depends(get_db),
):
    """Who opening `slots` places would let in, without letting them in.

    A GET because it changes nothing, and a separate call rather than a flag on
    the open endpoint: the panel shows this list and waits for a human to read
    it. Opening slots mints logins and sends email, so the one thing worth
    spending a round trip on is being sure about who.
    """
    require(admin.role, Capability.OPEN_WAITLIST_SLOTS)

    queue = next_in_queue(db, slots)
    pending_total = int(
        db.execute(
            select(func.count())
            .select_from(WaitlistRegistration)
            .where(WaitlistRegistration.status == PENDING)
        ).scalar_one()
    )
    cap = cap_status(db)
    # The preview reports the cap as it stands now, not as it would be. What
    # the admin is deciding is "these people, in", and a projected ceiling on
    # the same screen reads as though it had already moved.
    return SlotPreviewOut(
        slots=slots,
        would_approve=[RegistrationOut.model_validate(r) for r in queue],
        pending_total=pending_total,
        unused_slots=max(slots - len(queue), 0),
        cap=CapOut(**cap, can_grant_access=supabase_admin.is_configured()),
    )


@router.post("/slots/open", response_model=SlotsOpenedOut)
def open_waitlist_slots(
    payload: OpenSlotsRequest,
    admin: PanelAdmin = Depends(get_panel_admin),
    db: Session = Depends(get_db),
):
    """Open places and let the front of the queue into them.

    Not idempotent, and cannot be: each call is a separate decision to grow the
    list. Two clicks open twice as many slots, which is why the panel puts a
    named list of people behind a confirmation rather than a bare number behind
    a button.
    """
    require(admin.role, Capability.OPEN_WAITLIST_SLOTS)

    result = open_slots(
        db,
        slots=payload.slots,
        admin_id=admin.admin_id,
        admin_email=admin.email,
        admin_role=admin.role,
    )
    return SlotsOpenedOut(
        slots=result["slots"],
        approved=[RegistrationOut.model_validate(r) for r in result["approved"]],
        failures=[SlotFailureOut(**f) for f in result["failures"]],
        cap=CapOut(**result["cap"], can_grant_access=supabase_admin.is_configured()),
    )
