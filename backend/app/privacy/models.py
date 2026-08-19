"""Domain DTOs for the Privacy Center (data-subject rights).

Immutable frozen dataclasses -- the service returns these, never ORM rows, so the
persistence layer stays swappable.

Mapping to the rights being exercised:
    ExportBundle      GDPR Art 15 (access) + Art 20 (portability); DPDP s.11
    PrivacyState      Art 18 (restriction) + Art 17 (erasure) status for a founder
    PrivacyAction     the receipt returned for any right exercised, so the founder
                      always gets a reference and a due date rather than a silent OK
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ExportBundle:
    """Everything Ally holds about one founder, assembled for download."""

    founder_id: int
    generated_at: datetime
    # section name -> rows. A section present with an empty list means "we hold
    # nothing here", which is materially different from the section being absent.
    sections: dict[str, Any] = field(default_factory=dict)

    @property
    def record_count(self) -> int:
        return sum(len(v) if isinstance(v, list) else 1 for v in self.sections.values())


@dataclass(frozen=True)
class PrivacyState:
    """The founder's current standing under Art 17/18.

    `processing_restricted` pauses AI profiling without touching the account.
    `deletion_scheduled_at` is a future date, not an immediate purge -- see
    PrivacyService.request_account_deletion for why.
    """

    founder_id: int
    processing_restricted: bool
    processing_restricted_at: datetime | None
    deletion_requested_at: datetime | None
    deletion_scheduled_at: datetime | None
    deletion_executed_at: datetime | None = None

    @property
    def deletion_pending(self) -> bool:
        """Requested, and the sweep has not yet run. Distinct from merely
        "requested at some point" -- once executed, the request is history,
        not a pending state that should still gate processing (may_process)
        or read as cancellable."""
        return self.deletion_requested_at is not None and self.deletion_executed_at is None


@dataclass(frozen=True)
class PrivacyAction:
    """Receipt for an exercised right -- logged to privacy_requests.

    The fields below `due_by` exist for the admin resolution path
    (AdminPanelService.resolve_privacy_request): a "queued" request (view_data,
    correct_data) sits pending until an admin acts on it, and these are what
    they act with.
    """

    request_id: int
    founder_id: int
    request_type: str
    status: str
    requested_at: datetime
    due_by: datetime | None = None
    request_details: str | None = None
    processed_by: str | None = None
    processing_notes: str | None = None
    rejection_reason: str | None = None
    completed_at: datetime | None = None
