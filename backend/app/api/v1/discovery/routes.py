"""Discovery call endpoints.

Booking runs through Calendly in production; the calendar integration is stubbed
today (see app/services/calendar.py) so the flow works end to end. Swapping in
Calendly changes only that service -- these endpoints and the discovery_calls
storage stay the same.

    GET  /discovery/slots        available time slots (stub)
    POST /discovery/book         create a booking
    GET  /discovery/calls        the founder's calls
    GET  /discovery/calls/{id}   one call (confirmation)
    POST /discovery/calls/{id}/cancel      cancel a booked call
    POST /discovery/calls/{id}/reschedule  move it to another slot
"""

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_founder_record
from app.db.session import get_db
from app.middleware.error_handler import AppError
from app.models import Founder
from app.repositories import discovery_call_repository
from app.schemas.discovery import (
    BookingRequest,
    CallRead,
    CancelRequest,
    RescheduleRequest,
    SlotsResponse,
)
from app.services.calendar import DEFAULT_TIMEZONE, available_slots, create_meeting
from app.services.discovery_notifications import send_booking_confirmation
from app.api.v1.plans.dependencies import enforcement_enabled
from app.core.container import container
from app.core.logger import logger
from app.plans.catalog import (
    PRIORITY_CALL_LEAD_DAYS,
    STANDARD_CALL_LEAD_DAYS,
    Feature,
)
from app.plans.usage import period_month

router = APIRouter(prefix="/discovery", tags=["discovery"])


class CallNotFoundError(AppError):
    def __init__(self):
        super().__init__("Discovery call not found", status_code=status.HTTP_404_NOT_FOUND)


class SlotInPastError(AppError):
    def __init__(self):
        super().__init__("scheduled_at must be in the future", status_code=422)


class CallNotChangeableError(AppError):
    """The call has already been cancelled, completed, or has passed.

    Deliberately 409 rather than 404: the founder is looking at a real call of
    their own, and telling them it does not exist would be both wrong and
    alarming. The message names the state so they know which it was.
    """

    def __init__(self, state: str):
        super().__init__(f"This call cannot be changed because it is {state}.",
                         status_code=409)


def _has_call_priority(founder: Founder, db: Session) -> bool:
    """Does this founder hold the Rs 999 call perk?

    Read through the entitlement service rather than comparing plan_type, so the
    catalog stays the only place that decides which tiers carry it. Unlike the
    quota gate this is NOT behind enforcement_enabled: a priority lead is a perk
    being granted, not an allowance being refused, and leaving it dark would give
    every founder Pro's booking window.
    """
    return container.entitlement_service(db).has_feature(
        getattr(founder, "plan_type", None), Feature.PRIORITY_CALL
    )


@router.get("/slots", response_model=SlotsResponse)
async def get_slots(days: int = 7, founder: Founder = Depends(get_founder_record),
                    db: Session = Depends(get_db)):
    """Available booking slots. Stubbed; Calendly will own real availability.

    Pro's window opens two days earlier than everyone else's, which is what
    "priority booking" means here: the same slots, reached first.
    """
    days = max(1, min(days, 30))
    now = datetime.now(timezone.utc)
    lead = (PRIORITY_CALL_LEAD_DAYS if _has_call_priority(founder, db)
            else STANDARD_CALL_LEAD_DAYS)
    return SlotsResponse(timezone=DEFAULT_TIMEZONE,
                         slots=available_slots(now, days, lead_days=lead))


@router.post("/book", response_model=CallRead, status_code=status.HTTP_201_CREATED)
async def book_call(
    payload: BookingRequest,
    background: BackgroundTasks,
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
):
    """REQUEST a discovery call. The team confirms it; payment follows that.

    This used to book and confirm in one step, which did not match how the calls
    actually run and could not work at all under the current plans:

      * No plan includes a free call any more, so the entitlement gate refused
        every founder with a 402 and there was no way to pay past it -- checkout
        does not exist. Discovery calls were unbookable by anyone.
      * It created the Google Meet BEFORE the row was written. When the insert
        then failed (see the merge migration 499814b9067a -- `is_priority` had
        never been added to the table) the founder got a 500 and we were left
        with a meeting nobody was going to attend.

    So a founder now REQUESTS a slot and the row is written `pending`. Nothing is
    charged, no calendar event is created, and no allowance is consumed. The team
    confirms from the admin side, and only then is the meeting made and the
    founder emailed -- see `confirm_call` in the admin panel router.

    Slots offered are already the team's real availability: `available_slots`
    removes anything overlapping the host calendar's busy blocks.

    PAYMENT IS DELIBERATELY NOT HERE. It belongs after confirmation, through
    Razorpay, and is owned by whoever is building checkout for the subscription
    plans. The seam is `payment_reference` on the request and the `pending` ->
    `confirmed` transition; neither needs to change when payment lands.
    """
    scheduled = payload.scheduled_at
    if scheduled.tzinfo is None:
        scheduled = scheduled.replace(tzinfo=timezone.utc)
    if scheduled <= datetime.now(timezone.utc):
        raise SlotInPastError()

    data = {
        "founder_id": founder.founder_id,
        "scheduled_at": scheduled,
        # A request, not a booking. The founder is told this plainly in the UI:
        # nothing is agreed until the team confirms.
        "status": "pending",
        "booking_source": "founder_request",
        "notes_pre_call": payload.notes_pre_call,
        # Recorded on the row, not derived at read time: the founder's plan can
        # change after the request, and what the queue needs to know is whether
        # this request was priority WHEN IT WAS MADE.
        "is_priority": _has_call_priority(founder, db),
    }
    if payload.timezone:
        data["timezone"] = payload.timezone
    return discovery_call_repository.create(db, data)


@router.get("/calls", response_model=list[CallRead])
async def list_calls(
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
):
    """The signed-in founder's discovery calls."""
    return discovery_call_repository.list_for_founder(db, founder.founder_id)


@router.get("/calls/{call_id}", response_model=CallRead)
async def get_call(
    call_id: int,
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
):
    """One discovery call -- the booking confirmation."""
    call = discovery_call_repository.get(db, call_id)
    # Never leak another founder's booking.
    if call is None or call.founder_id != founder.founder_id:
        raise CallNotFoundError()
    return call


#: Statuses a founder may still act on. `pending` is included because a call
#: awaiting confirmation is exactly the one somebody is most likely to change.
_CHANGEABLE = {"pending", "confirmed"}


def _owned_changeable_call(db: Session, founder: Founder, call_id: int):
    """The founder's own call, if it is still theirs to change.

    Ownership first, then state. A call belonging to someone else is a 404 --
    never confirm that another founder's booking exists.
    """
    call = discovery_call_repository.get(db, call_id)
    if call is None or call.founder_id != founder.founder_id:
        raise CallNotFoundError()
    if call.status not in _CHANGEABLE:
        raise CallNotChangeableError(call.status)
    if call.scheduled_at <= datetime.now(timezone.utc):
        raise CallNotChangeableError("already in the past")
    return call


# NOTE ON ALLOWANCES AND REFUNDS
#
# Nothing consumes a call allowance any more. Requesting is free, and confirming
# is a team action -- so a cancellation has nothing to give back, and a refund
# here would credit a call that was never taken.
#
# When payment lands (Razorpay, owned by whoever is building checkout), the
# consume belongs next to the confirm, and the matching release belongs in
# `cancel_call` below. They are a pair: add them together or neither.


@router.post("/calls/{call_id}/cancel", response_model=CallRead)
async def cancel_call(
    call_id: int,
    payload: CancelRequest,
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
):
    """Cancel a booked call.

    There was no way to do this at all: a founder who booked a 30-minute call
    three days out and then had their week change had to email support, and
    every one of those became a ticket. The slot also stayed blocked, so nobody
    else could take it.

    The row is kept rather than deleted -- status becomes `cancelled` with the
    time and the reason -- because a cancelled call is part of the founder's
    history and the host needs to know it happened.
    """
    call = _owned_changeable_call(db, founder, call_id)

    discovery_call_repository.update(db, call, {
        "status": "cancelled",
        "cancelled_at": datetime.now(timezone.utc),
        "cancellation_reason": payload.reason,
    })
    return call


@router.post("/calls/{call_id}/reschedule", response_model=CallRead,
             status_code=status.HTTP_201_CREATED)
async def reschedule_call(
    call_id: int,
    payload: RescheduleRequest,
    background: BackgroundTasks,
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
):
    """Move a booked call to a different slot.

    Cancel-then-rebook rather than editing in place, so the trail survives: the
    old row becomes `cancelled` and the new one points back at it through
    `rescheduled_from_call_id`. A call that moved twice reads as two moves
    afterwards, not as one row that quietly changed its mind.

    No entitlement is charged. The founder already has this call -- moving it is
    not a second booking, and charging for it would make rescheduling something
    people avoid by simply not turning up.
    """
    scheduled = payload.scheduled_at
    if scheduled.tzinfo is None:
        scheduled = scheduled.replace(tzinfo=timezone.utc)
    if scheduled <= datetime.now(timezone.utc):
        raise SlotInPastError()

    old = _owned_changeable_call(db, founder, call_id)

    # A moved request is still a request. Only a call the team had already
    # confirmed gets a new meeting -- creating one for a pending request would
    # put an event on the host calendar for a call nobody has agreed to yet,
    # which is the thing this whole flow was changed to stop.
    was_confirmed = old.status == "confirmed"
    meeting = None
    if was_confirmed:
        # New meeting first. If the calendar refuses, the founder still has the
        # call they started with rather than neither.
        meeting = create_meeting(founder.founder_id, scheduled, founder_email=founder.email)

    new_call = discovery_call_repository.create(db, {
        "founder_id": founder.founder_id,
        "scheduled_at": scheduled,
        "status": "confirmed" if was_confirmed else "pending",
        "meeting_link": meeting["meeting_link"] if meeting else None,
        "goxml_host": meeting["host"] if meeting else None,
        "booking_source": meeting["provider"] if meeting else "founder_request",
        "notes_pre_call": old.notes_pre_call,
        "timezone": old.timezone,
        # Carried from the original booking, not recomputed: this is the same
        # request as before, so it keeps the priority it was made with.
        "is_priority": old.is_priority,
        "rescheduled_from_call_id": old.call_id,
    })

    discovery_call_repository.update(db, old, {
        "status": "rescheduled",
        "cancelled_at": datetime.now(timezone.utc),
        "cancellation_reason": payload.reason or "Rescheduled by the founder",
    })

    # Only a confirmed call has anything to confirm. A moved request is still
    # waiting on the team, and emailing "your call is booked" would be a lie.
    if was_confirmed and founder.email:
        background.add_task(
            send_booking_confirmation,
            founder.email, founder.full_name, new_call.scheduled_at, new_call.meeting_link,
        )
    return new_call
