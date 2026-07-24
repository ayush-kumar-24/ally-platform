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

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_founder_record
from app.db.session import get_db
from app.middleware.error_handler import AppError
from app.models import Founder
from app.repositories import discovery_call_repository
from app.schemas.discovery import BookingRequest, CallRead, SlotsResponse
from app.services.calendar import DEFAULT_TIMEZONE, available_slots, create_meeting

router = APIRouter(prefix="/discovery", tags=["discovery"])


class CallNotFoundError(AppError):
    def __init__(self):
        super().__init__("Discovery call not found", status_code=status.HTTP_404_NOT_FOUND)


class SlotInPastError(AppError):
    def __init__(self):
        super().__init__("scheduled_at must be in the future", status_code=422)


@router.get("/slots", response_model=SlotsResponse)
async def get_slots(days: int = 7, founder: Founder = Depends(get_founder_record)):
    """Available booking slots. Stubbed; Calendly will own real availability."""
    days = max(1, min(days, 30))
    now = datetime.now(timezone.utc)
    return SlotsResponse(timezone=DEFAULT_TIMEZONE, slots=available_slots(now, days))


@router.post("/book", response_model=CallRead, status_code=status.HTTP_201_CREATED)
async def book_call(
    payload: BookingRequest,
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
):
    """Book a discovery call. Creates the meeting (stub) and records it."""
    scheduled = payload.scheduled_at
    if scheduled.tzinfo is None:
        scheduled = scheduled.replace(tzinfo=timezone.utc)
    if scheduled <= datetime.now(timezone.utc):
        raise SlotInPastError()

    meeting = create_meeting(founder.founder_id, scheduled, founder_email=founder.email)
    data = {
        "founder_id": founder.founder_id,
        "scheduled_at": scheduled,
        "status": "confirmed",
        "meeting_link": meeting["meeting_link"],
        "goxml_host": meeting["host"],
        "booking_source": meeting["provider"],
        "notes_pre_call": payload.notes_pre_call,
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
