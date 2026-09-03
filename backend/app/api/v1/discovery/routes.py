"""Discovery call endpoints.

Booking runs through Calendly in production; the calendar integration is stubbed
today (see app/services/calendar.py) so the flow works end to end. Swapping in
Calendly changes only that service -- these endpoints and the discovery_calls
storage stay the same.

    GET  /discovery/slots        available time slots (stub)
    POST /discovery/book         create a booking
    GET  /discovery/calls        the founder's calls
    GET  /discovery/calls/{id}   one call (confirmation)
"""

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_founder_record
from app.db.session import get_db
from app.middleware.error_handler import AppError
from app.models import Founder
from app.repositories import discovery_call_repository
from app.schemas.discovery import BookingRequest, CallRead, SlotsResponse
from app.services.calendar import DEFAULT_TIMEZONE, available_slots, create_meeting
from app.services.discovery_notifications import send_booking_confirmation
from app.api.v1.plans.dependencies import enforcement_enabled
from app.core.container import container
from app.plans.catalog import (
    CALL_PRICE_INR,
    PRIORITY_CALL_LEAD_DAYS,
    STANDARD_CALL_LEAD_DAYS,
    Feature,
)
from app.plans.errors import NoFreeCallsRemainingError
from app.plans.usage import period_month

router = APIRouter(prefix="/discovery", tags=["discovery"])


class CallNotFoundError(AppError):
    def __init__(self):
        super().__init__("Discovery call not found", status_code=status.HTTP_404_NOT_FOUND)


class SlotInPastError(AppError):
    def __init__(self):
        super().__init__("scheduled_at must be in the future", status_code=422)


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
    """Book a discovery call: create the calendar event, record it, and email a
    confirmation (in the background, so email never blocks or breaks booking)."""
    scheduled = payload.scheduled_at
    if scheduled.tzinfo is None:
        scheduled = scheduled.replace(tzinfo=timezone.utc)
    if scheduled <= datetime.now(timezone.utc):
        raise SlotInPastError()

    # --- entitlement ------------------------------------------------------
    # Everyone may book; only whether it is free differs by plan. The free call is
    # CLAIMED BEFORE the booking is created, because the claim is the thing that
    # must not be raced -- two simultaneous bookings must not both take the last
    # free call. If anything after this point fails, the claim is released so a
    # transient calendar error never silently eats a founder's monthly allowance.
    claimed_free = False
    if enforcement_enabled():
        entitlements = container.entitlement_service(db)
        quote = entitlements.quote_call(founder.founder_id, getattr(founder, "plan_type", None))
        if quote.is_free:
            entitlements.consume_free_call(founder.founder_id, getattr(founder, "plan_type", None))
            claimed_free = True
        elif not payload.payment_reference:
            # No free calls left and no proof of payment -- refuse with the price
            # rather than booking something nobody paid for.
            raise NoFreeCallsRemainingError(
                used=entitlements.usage.get_calls(
                    founder.founder_id, period_month(datetime.now(timezone.utc))
                ).free_calls_used,
                allowance=entitlements.plan_for(
                    getattr(founder, "plan_type", None)).free_calls_per_month,
                price=CALL_PRICE_INR,
            )

    try:
        meeting = create_meeting(founder.founder_id, scheduled, founder_email=founder.email)
    except Exception:
        if claimed_free:
            entitlements.usage.release_free_call(
                founder.founder_id, period_month(datetime.now(timezone.utc)),
                at=datetime.now(timezone.utc))
        raise

    data = {
        "founder_id": founder.founder_id,
        "scheduled_at": scheduled,
        "status": "confirmed",
        "meeting_link": meeting["meeting_link"],
        "goxml_host": meeting["host"],
        "booking_source": meeting["provider"],
        "notes_pre_call": payload.notes_pre_call,
        # Recorded on the row, not derived at read time: the founder's plan can
        # change after booking, and what the queue needs to know is whether this
        # request was priority WHEN IT WAS MADE.
        "is_priority": _has_call_priority(founder, db),
    }
    if payload.timezone:
        data["timezone"] = payload.timezone
    try:
        call = discovery_call_repository.create(db, data)
    except Exception:
        if claimed_free:
            entitlements.usage.release_free_call(
                founder.founder_id, period_month(datetime.now(timezone.utc)),
                at=datetime.now(timezone.utc))
        raise

    if founder.email:
        background.add_task(
            send_booking_confirmation,
            founder.email, founder.full_name, call.scheduled_at, call.meeting_link,
        )
    return call


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
