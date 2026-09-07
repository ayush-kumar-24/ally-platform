"""Pydantic schemas for the Privacy Center.

Maps 1:1 to the privacy_requests table. Allowed request_type values are
enforced by a database CHECK constraint; we mirror them here so the API
surfaces a meaningful validation error before hitting the DB.
"""

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

#: What a founder may POST to /settings/privacy -- the rights that need a human
#: to action them.
#:
#: DELIBERATELY NARROWER THAN THE DB CONSTRAINT. The table also allows
#: `delete_account` and `cancel_deletion`, but those are written by the erasure
#: service, which schedules the deletion, sets the grace period and records the
#: consent trail. Accepting them here would let a founder queue a row that looks
#: like a deletion request while none of that happened -- a deletion we would
#: believe we had and never perform. They stay out on purpose.
PrivacyRequestType = Literal[
    "view_data",
    "download_data",
    "correct_data",
    "withdraw_consent",
    "restrict_processing",
    "portability",
    "email_change",
    "grievance",
]

PrivacyRequestStatus = Literal["pending", "in_progress", "completed", "rejected"]

#: Deliberately permissive. This is not the place to adjudicate what a valid
#: address is -- a human reads the request and the real test is whether mail
#: arrives. It exists to catch the obvious ("no", "same as before", a phone
#: number), because an email-change request with no address in it is
#: unactionable and the founder cannot be asked to clarify: the address we hold
#: is the thing that is broken.
_LOOKS_LIKE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class PrivacyRequestCreate(BaseModel):
    """Body the founder sends to submit a new privacy request."""

    model_config = ConfigDict(extra="forbid")

    request_type: PrivacyRequestType
    request_details: str | None = Field(
        default=None,
        max_length=2000,
        description=(
            "Freetext the founder wants to include (e.g. specific fields to "
            "correct). REQUIRED for email_change, where it must be the new "
            "address and nothing else."
        ),
    )

    @model_validator(mode="after")
    def _grievance_says_what_is_wrong(self) -> "PrivacyRequestCreate":
        """A complaint with no complaint in it cannot be acknowledged or resolved.

        Enforced here rather than left to the Grievance Officer, because an
        empty grievance still starts the statutory clock and still has to be
        answered -- with nothing to answer about.
        """
        if self.request_type != "grievance":
            return self
        if not (self.request_details or "").strip():
            raise ValueError("Please tell us what went wrong so we can look into it.")
        return self

    @model_validator(mode="after")
    def _email_change_carries_an_address(self) -> "PrivacyRequestCreate":
        """An email_change request must say which address to change it to.

        Enforced here rather than left to the admin because the admin's only
        recourse for an empty one is to ask the founder -- at the address that
        does not work. The request would sit in the queue forever.
        """
        if self.request_type != "email_change":
            return self
        value = (self.request_details or "").strip()
        if not value:
            raise ValueError("An email change request must include the new email address.")
        if not _LOOKS_LIKE_EMAIL.fullmatch(value):
            raise ValueError(
                "Enter just the new email address, e.g. you@example.com."
            )
        self.request_details = value.lower()
        return self


class PrivacyRequestRead(BaseModel):
    """One privacy request row returned to the founder."""

    model_config = ConfigDict(from_attributes=True)

    request_id: int
    request_type: str
    status: str
    request_details: str | None = None
    processing_notes: str | None = None
    rejection_reason: str | None = None
    due_by: datetime | None = None
    completed_at: datetime | None = None
    requested_at: datetime
    created_at: datetime | None = None


class PrivacyRequestListResponse(BaseModel):
    """Paginated list of privacy requests for the signed-in founder."""

    items: list[PrivacyRequestRead]
    total: int
