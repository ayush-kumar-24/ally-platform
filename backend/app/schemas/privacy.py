"""Pydantic schemas for the Privacy Center.

Maps 1:1 to the privacy_requests table. Allowed request_type values are
enforced by a database CHECK constraint; we mirror them here so the API
surfaces a meaningful validation error before hitting the DB.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# The six right types the DB constraint allows.
PrivacyRequestType = Literal[
    "view_data",
    "download_data",
    "correct_data",
    "withdraw_consent",
    "restrict_processing",
    "portability",
]

PrivacyRequestStatus = Literal["pending", "in_progress", "completed", "rejected"]


class PrivacyRequestCreate(BaseModel):
    """Body the founder sends to submit a new privacy request."""

    model_config = ConfigDict(extra="forbid")

    request_type: PrivacyRequestType
    request_details: str | None = Field(
        default=None,
        max_length=2000,
        description="Optional freetext the founder wants to include (e.g. specific fields to correct).",
    )


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
