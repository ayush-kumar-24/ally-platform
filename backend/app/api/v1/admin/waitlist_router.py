"""Team-side handling of waitlist registrations -- the screen where access is
actually granted.

    GET  /admin/waitlist                the queue, oldest request first
    POST /admin/waitlist/{id}/approve   create their login and email them
    POST /admin/waitlist/{id}/reject    turn it down, with a reason

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
from app.models.waitlist import STATUSES, WaitlistRegistration
from app.services import supabase_admin
from app.services.waitlist import approve, cap_status, reject

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
