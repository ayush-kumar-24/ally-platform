"""Discovery call endpoints.

Booking is self-serve and immediate: the founder picks one of the fixed slots we
publish, the meeting is created, and the confirmation email goes out. Nobody has
to approve it.

Availability comes from app/services/calendar.py -- a fixed weekday grid, minus
anything the host calendar is already busy with, minus anything another founder
has taken.

    GET  /discovery/slots        available time slots (stub)
    POST /discovery/book         create a booking
    GET  /discovery/calls        the founder's calls
    GET  /discovery/calls/{id}   one call (confirmation)
    POST /discovery/calls/{id}/cancel      cancel a booked call
    POST /discovery/calls/{id}/reschedule  move it to another slot
"""

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy import text as _sql
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
from app.notifications import notify
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


class SlotNotOfferedError(AppError):
    """A time that is not one of the published slots.

    Mattered less when a human confirmed every request and could simply decline
    an odd one. Now that booking confirms itself, this is the only thing between
    us and a founder holding a confirmed 3am Sunday call.
    """

    def __init__(self):
        super().__init__(
            "That time is not one of our available slots. Pick one from the list.",
            status_code=422,
        )


class SlotTakenError(AppError):
    """Somebody else got there first.

    409 rather than 422: nothing is wrong with the request, the world just
    changed between the founder loading the page and pressing the button.
    """

    def __init__(self):
        super().__init__(
            "Someone just booked that slot. Please choose another time.",
            status_code=409,
        )


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


# Namespace for the advisory locks below, so a slot lock can never collide with
# some other advisory lock added later. Arbitrary, just has to be unique.
_SLOT_LOCK_NAMESPACE = 4711


def _claim_slot(db: Session, scheduled: datetime, founder: Founder,
                exclude_call_id: int | None = None) -> None:
    """Refuse the booking unless this exact slot is published and still free.

    WHY A LOCK. Two founders pressing Book on the same slot within the same
    second would both read "nothing booked here" and both be confirmed, and
    with no human approving requests any more there is nothing downstream to
    catch it. The advisory lock is taken on the slot itself, so it serialises
    only the founders competing for that one time and holds until this
    transaction ends.
    """
    minute_key = int(scheduled.timestamp()) // 60      # fits int4 for ~4000 years
    db.execute(_sql("select pg_advisory_xact_lock(:ns, :key)"),
               {"ns": _SLOT_LOCK_NAMESPACE, "key": minute_key})

    # Published grid, over the whole bookable window rather than the 7 days the
    # page happens to show, so a founder deep-linking a real later slot is not
    # refused for a time we would have offered.
    lead = (PRIORITY_CALL_LEAD_DAYS if _has_call_priority(founder, db)
            else STANDARD_CALL_LEAD_DAYS)
    offered = available_slots(datetime.now(timezone.utc), 30, lead_days=lead)
    if scheduled not in offered:
        raise SlotNotOfferedError()

    # 'rescheduled' is not here on purpose: that row has been superseded by the
    # new one it points at, so it no longer holds its old time.
    sql = """
        select call_id from discovery_calls
         where scheduled_at = :at
           and status in ('pending', 'confirmed')
    """
    params = {"at": scheduled}
    if exclude_call_id is not None:
        sql += " and call_id <> :exclude"
        params["exclude"] = exclude_call_id
    if db.execute(_sql(sql + " limit 1"), params).first():
        raise SlotTakenError()


def _send_confirmation(founder_email: str | None, name: str | None,
                       scheduled: datetime, link: str | None, call_id: int) -> None:
    """Email the founder. Never raises -- the call is booked either way.

    Runs in a background task so a slow mail server does not hold the founder on
    a spinner after their booking has already been written.
    """
    if not founder_email:
        return
    try:
        send_booking_confirmation(founder_email, name, scheduled, link)
    except Exception:                                  # noqa: BLE001
        logger.warning("discovery confirmation email failed",
                       extra={"call_id": call_id})


@router.get("/slots", response_model=SlotsResponse)
def get_slots(days: int = 7, founder: Founder = Depends(get_founder_record),
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
def book_call(
    payload: BookingRequest,
    background: BackgroundTasks,
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
):
    """Book a discovery call. Confirmed immediately -- no approval step.

    HOW THIS USED TO WORK, AND WHY IT CHANGED. A founder used to REQUEST a slot;
    the row was written `pending`, it appeared in an admin queue, and somebody on
    the team had to press Confirm before the meeting was created and the email
    sent. That was built when no plan included a call and payment was expected to
    sit in the gap. It made every booking wait on a person, and a founder who
    booked on Friday evening heard nothing until Monday.

    Now: the slots we publish ARE the offer. Picking one books it.

    ORDER MATTERS. The meeting is created before the row is written, so a
    calendar failure means the founder sees an error and can try again, rather
    than holding a confirmed call with no way to join it. Nothing is left behind
    on the calendar that way either -- the insert is what makes it real.

    STILL FREE. Nothing is charged and no allowance is consumed, which is the
    same as before; removing the approval step did not add a payment step. When
    checkout exists, the charge belongs immediately before `create_meeting` here
    and the refund belongs in `cancel_call`.
    """
    scheduled = payload.scheduled_at
    if scheduled.tzinfo is None:
        scheduled = scheduled.replace(tzinfo=timezone.utc)
    if scheduled <= datetime.now(timezone.utc):
        raise SlotInPastError()

    # Held for the rest of this transaction, so the check and the insert below
    # cannot be interleaved with another founder taking the same slot.
    _claim_slot(db, scheduled, founder)

    meeting = create_meeting(
        founder.founder_id, scheduled, founder_email=getattr(founder, "email", None),
    )

    data = {
        "founder_id": founder.founder_id,
        "scheduled_at": scheduled,
        "status": "confirmed",
        "meeting_link": meeting["meeting_link"],
        "goxml_host": meeting["host"],
        "booking_source": meeting["provider"],
        "notes_pre_call": payload.notes_pre_call,
        # Stamped at booking time, not derived later: the founder's plan can
        # change afterwards, and what matters is what was true when they booked.
        "is_priority": _has_call_priority(founder, db),
    }
    if payload.timezone:
        data["timezone"] = payload.timezone
    call = discovery_call_repository.create(db, data)

    # The bell as well as the email. A founder who has Ally open when they book
    # should not have to go to their inbox to see that it worked.
    notify(
        db, founder_id=founder.founder_id, type="discovery_call_confirmed",
        title="Your discovery call is booked",
        body=("Your call is confirmed. The joining link is on the Discovery call "
              "page, and it is in the email we just sent you."),
        action_url="/app/discovery-call",
        dedup_key=f"discovery_call_confirmed:{call.call_id}",
    )

    background.add_task(
        _send_confirmation, getattr(founder, "email", None),
        getattr(founder, "full_name", None), scheduled, call.meeting_link,
        call.call_id,
    )
    return call


@router.get("/calls", response_model=list[CallRead])
def list_calls(
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
):
    """The signed-in founder's discovery calls."""
    return discovery_call_repository.list_for_founder(db, founder.founder_id)


@router.get("/calls/{call_id}", response_model=CallRead)
def get_call(
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
def cancel_call(
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
def reschedule_call(
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

    # Same two rules as booking: it has to be a slot we publish, and it has to
    # still be free. Excluding this call's own row, so moving a call to the time
    # it already holds is not refused as a clash with itself.
    _claim_slot(db, scheduled, founder, exclude_call_id=call_id)

    # New meeting first. If the calendar refuses, the founder still has the call
    # they started with rather than neither.
    #
    # `was_confirmed` survives for rows created before booking confirmed itself:
    # anything still sitting `pending` from the old approval queue keeps that
    # status when it moves, rather than being silently upgraded by a reschedule.
    was_confirmed = old.status == "confirmed"
    meeting = None
    if was_confirmed:
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
