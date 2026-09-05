"""Team-side handling of founders' discovery-call requests.

A founder picks a slot from the team's real availability and that creates a
`pending` REQUEST -- nothing is booked, nothing is charged, and no calendar
event exists yet. This is the other half: the team confirms the request, which
is the point at which the meeting is actually created and the founder told.

Why the meeting is made here and not at request time: the previous flow created
a Google Meet before writing the row, so a failed insert left a real meeting on
the host calendar that nobody was going to attend. Making it at confirmation
means an event exists only for calls that are genuinely happening.

Payment sits after this transition and is owned by whoever is building Razorpay
for the subscription plans. Nothing here needs to change when it lands: confirm
stays the moment the team accepts, and the payment step hangs off it.

    GET  /admin/discovery-calls              the queue, newest request first
    POST /admin/discovery-calls/{id}/confirm accept it and create the meeting
    POST /admin/discovery-calls/{id}/decline turn it down, with a reason
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin.rbac import Capability, require
from app.api.v1.admin.panel_dependencies import client_ip, get_panel_admin, get_panel_service
from app.api.v1.admin.panel_dependencies import PanelAdmin
from app.core.logger import logger
from app.db.session import get_db
from app.middleware.error_handler import AppError
from app.models import Founder
from app.models.schema import DiscoveryCalls
from app.schemas.discovery import CallRead
from app.services.calendar import create_meeting
from app.services.discovery_notifications import send_booking_confirmation

router = APIRouter(prefix="/admin/discovery-calls", tags=["admin"])

#: Only a request can be confirmed or declined. Anything already settled is left
#: alone -- re-confirming a confirmed call would mint a second meeting link.
_PENDING = "pending"


class CallNotPendingError(AppError):
    def __init__(self, state: str):
        super().__init__(
            f"This call is {state}, so it is no longer a request that can be answered.",
            status_code=409,
        )


class CallRequestNotFoundError(AppError):
    def __init__(self):
        super().__init__("Discovery call request not found", status_code=404)


class DeclineRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    #: Shown to nobody automatically -- it is recorded so the team can say why
    #: when they follow up. Required, because "declined, no reason" is not a
    #: thing a founder should ever be left with.
    reason: str = Field(min_length=1, max_length=500)


class CallRequestRow(CallRead):
    """A queue row: the call plus who asked for it."""

    founder_id: int
    founder_name: str | None = None
    founder_email: str | None = None
    is_priority: bool = False


def _pending_call(db: Session, call_id: int) -> DiscoveryCalls:
    call = db.get(DiscoveryCalls, call_id)
    if call is None:
        raise CallRequestNotFoundError()
    if call.status != _PENDING:
        raise CallNotPendingError(call.status)
    return call


@router.get("", response_model=list[CallRequestRow],
            summary="Discovery-call requests waiting on the team")
def list_requests(
    only_pending: bool = Query(default=True),
    limit: int = Query(default=50, ge=1, le=200),
    admin: PanelAdmin = Depends(get_panel_admin),
    db: Session = Depends(get_db),
) -> list[CallRequestRow]:
    """The queue. Priority requests first, then soonest slot.

    Ordered by the slot rather than by when it was asked for: a request for
    Tuesday needs answering before one for next month, whoever asked first.
    """
    require(admin.role, Capability.MANAGE_DISCOVERY_CALLS)

    stmt = select(DiscoveryCalls, Founder).join(
        Founder, Founder.founder_id == DiscoveryCalls.founder_id
    )
    if only_pending:
        stmt = stmt.where(DiscoveryCalls.status == _PENDING)
    stmt = stmt.order_by(
        DiscoveryCalls.is_priority.desc(), DiscoveryCalls.scheduled_at.asc()
    ).limit(limit)

    return [
        CallRequestRow(
            call_id=c.call_id, status=c.status, scheduled_at=c.scheduled_at,
            duration_minutes=c.duration_minutes, timezone=c.timezone,
            meeting_link=c.meeting_link, goxml_host=c.goxml_host,
            booking_source=c.booking_source, notes_pre_call=c.notes_pre_call,
            created_at=c.created_at,
            founder_id=c.founder_id,
            founder_name=getattr(f, "full_name", None),
            founder_email=getattr(f, "email", None),
            is_priority=bool(c.is_priority),
        )
        for c, f in db.execute(stmt).all()
    ]


@router.post("/{call_id}/confirm", response_model=CallRead,
             summary="Confirm a request: create the meeting and tell the founder")
def confirm_call(
    call_id: int,
    ip: str | None = Depends(client_ip),
    admin: PanelAdmin = Depends(get_panel_admin),
    service=Depends(get_panel_service),
    db: Session = Depends(get_db),
) -> CallRead:
    """Accept a request.

    Order matters. The meeting is created first: if the calendar refuses, the
    request stays `pending` and the team can try again, rather than the founder
    holding a "confirmed" call with no way to join it.
    """
    require(admin.role, Capability.MANAGE_DISCOVERY_CALLS)
    call = _pending_call(db, call_id)
    founder = db.get(Founder, call.founder_id)

    meeting = create_meeting(
        call.founder_id, call.scheduled_at,
        founder_email=getattr(founder, "email", None),
    )

    call.status = "confirmed"
    call.meeting_link = meeting["meeting_link"]
    call.goxml_host = meeting["host"]
    call.booking_source = meeting["provider"]
    db.commit()
    db.refresh(call)

    service.audit.record(
        admin=admin, action="discovery_call.confirm",
        resource=f"discovery_call:{call_id}", target_user_id=call.founder_id,
        ip_address=ip, new_value={"scheduled_at": call.scheduled_at.isoformat()},
    )

    email = getattr(founder, "email", None)
    if email:
        try:
            send_booking_confirmation(
                email, getattr(founder, "full_name", None),
                call.scheduled_at, call.meeting_link,
            )
        except Exception:
            # The call is confirmed either way. A failed email is worth knowing
            # about but must not undo a booking the team has just agreed to.
            logger.warning("discovery confirmation email failed",
                           extra={"call_id": call_id, "founder_id": call.founder_id})
    return call


@router.post("/{call_id}/decline", response_model=CallRead,
             status_code=status.HTTP_200_OK,
             summary="Decline a request, with a reason")
def decline_call(
    call_id: int,
    payload: DeclineRequest,
    ip: str | None = Depends(client_ip),
    admin: PanelAdmin = Depends(get_panel_admin),
    service=Depends(get_panel_service),
    db: Session = Depends(get_db),
) -> CallRead:
    """Turn a request down.

    Recorded as `cancelled` with the reason, rather than deleted: the founder
    asked for something and is owed an answer, and the team needs to see what
    was said when they follow up.
    """
    require(admin.role, Capability.MANAGE_DISCOVERY_CALLS)
    call = _pending_call(db, call_id)

    call.status = "cancelled"
    call.cancelled_at = datetime.now(timezone.utc)
    call.cancellation_reason = payload.reason
    db.commit()
    db.refresh(call)

    service.audit.record(
        admin=admin, action="discovery_call.decline",
        resource=f"discovery_call:{call_id}", target_user_id=call.founder_id,
        ip_address=ip, new_value={"reason": payload.reason},
    )
    return call
