from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SlotsResponse(BaseModel):
    timezone: str
    slots: list[datetime]


class BookingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scheduled_at: datetime
    timezone: str | None = Field(default=None, max_length=64)
    notes_pre_call: str | None = Field(default=None, max_length=2000)
    # Present once the founder has paid for a call beyond their free allowance.
    # Payments are not wired yet, so today this is how a paid booking is asserted;
    # when the gateway lands it becomes the gateway's reference to verify.
    payment_reference: str | None = Field(default=None, max_length=100)


class CallRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    call_id: int
    status: str
    scheduled_at: datetime
    duration_minutes: int
    timezone: str
    meeting_link: str | None = None
    goxml_host: str | None = None
    booking_source: str | None = None
    notes_pre_call: str | None = None
    created_at: datetime | None = None


class CancelRequest(BaseModel):
    """Why the founder is cancelling. Optional -- never block a cancellation on
    making someone explain themselves."""

    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=500)


class RescheduleRequest(BaseModel):
    """Move a booked call to a different slot.

    Modelled as cancel-then-book rather than an in-place edit: the old row is
    kept as `cancelled` and the new one records `rescheduled_from_call_id`, so
    the history of a call that moved three times is still readable afterwards.
    """

    model_config = ConfigDict(extra="forbid")

    scheduled_at: datetime
    reason: str | None = Field(default=None, max_length=500)
