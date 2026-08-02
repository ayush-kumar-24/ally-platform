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
