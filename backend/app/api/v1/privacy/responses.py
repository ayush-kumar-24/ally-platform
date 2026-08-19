"""Response models for the Privacy Center endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.privacy.models import DataSummary, ExportBundle, PrivacyAction, PrivacyState


class PrivacyActionResponse(BaseModel):
    request_id: int
    request_type: str
    status: str
    requested_at: datetime
    due_by: datetime | None = None

    @classmethod
    def from_domain(cls, a: PrivacyAction) -> "PrivacyActionResponse":
        return cls(request_id=a.request_id, request_type=a.request_type, status=a.status,
                   requested_at=a.requested_at, due_by=a.due_by)


class PrivacyStateResponse(BaseModel):
    founder_id: int
    processing_restricted: bool
    processing_restricted_at: datetime | None = None
    deletion_requested_at: datetime | None = None
    deletion_scheduled_at: datetime | None = None
    deletion_pending: bool

    @classmethod
    def from_domain(cls, s: PrivacyState) -> "PrivacyStateResponse":
        return cls(
            founder_id=s.founder_id,
            processing_restricted=s.processing_restricted,
            processing_restricted_at=s.processing_restricted_at,
            deletion_requested_at=s.deletion_requested_at,
            deletion_scheduled_at=s.deletion_scheduled_at,
            deletion_pending=s.deletion_pending,
        )


class PrivacyActionResult(BaseModel):
    """What every right-exercising endpoint returns: the new standing plus the
    receipt, so the UI can both re-render state and show a reference."""

    state: PrivacyStateResponse
    request: PrivacyActionResponse
    message: str


class ExportResponse(BaseModel):
    founder_id: int
    generated_at: datetime
    record_count: int
    sections: dict[str, Any]
    request: PrivacyActionResponse

    @classmethod
    def from_domain(cls, b: ExportBundle, a: PrivacyAction) -> "ExportResponse":
        return cls(founder_id=b.founder_id, generated_at=b.generated_at,
                   record_count=b.record_count, sections=b.sections,
                   request=PrivacyActionResponse.from_domain(a))


class DataSummaryResponse(BaseModel):
    founder_id: int
    generated_at: datetime
    total_records: int
    counts: dict[str, int]
    request: PrivacyActionResponse

    @classmethod
    def from_domain(cls, s: DataSummary, a: PrivacyAction) -> "DataSummaryResponse":
        return cls(founder_id=s.founder_id, generated_at=s.generated_at,
                   total_records=s.total_records, counts=s.counts,
                   request=PrivacyActionResponse.from_domain(a))
