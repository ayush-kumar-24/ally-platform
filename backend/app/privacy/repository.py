"""Privacy persistence seam.

`PrivacyRepository` is the interface the service depends on. Two implementations:
  * InMemoryPrivacyRepository -- deterministic, thread-safe, offline (used by tests).
  * SqlAlchemyPrivacyRepository (db_repository.py) -- the production store.
Swapping one for the other is a repository replacement only; the service is unchanged.
"""

from __future__ import annotations

import abc
import threading
from dataclasses import replace
from datetime import datetime

from app.privacy.errors import NoDeletionToCancelError, PrivacyRequestNotFoundError
from app.privacy.models import ExportBundle, PrivacyAction, PrivacyState


class PrivacyRepository(abc.ABC):
    @abc.abstractmethod
    def gather_export(self, founder_id: int, generated_at: datetime) -> ExportBundle:
        """Assemble everything held about the founder."""

    @abc.abstractmethod
    def get_state(self, founder_id: int) -> PrivacyState:
        """Current restriction / deletion standing."""

    @abc.abstractmethod
    def set_restriction(self, founder_id: int, *, restricted: bool, at: datetime) -> PrivacyState: ...

    @abc.abstractmethod
    def schedule_deletion(self, founder_id: int, *, requested_at: datetime,
                          scheduled_at: datetime) -> PrivacyState: ...

    @abc.abstractmethod
    def log_request(self, founder_id: int, *, request_type: str, details: str | None,
                    at: datetime, due_by: datetime | None) -> PrivacyAction:
        """Append to the privacy_requests audit trail."""

    @abc.abstractmethod
    def list_requests(self, founder_id: int) -> list[PrivacyAction]: ...

    @abc.abstractmethod
    def find_due_for_deletion(self, now: datetime) -> list[int]:
        """founder_ids whose grace window has passed and whose sweep has not
        yet run -- deletion_scheduled_at <= now AND deletion_executed_at IS
        NULL. The scheduled-sweep caller's whole worklist."""

    @abc.abstractmethod
    def cancel_deletion(self, founder_id: int) -> PrivacyState:
        """Clear a pending (not-yet-executed) deletion request. Refuses
        silently-doing-nothing-useful once deletion_executed_at is set --
        the sweep already ran, there is nothing left to cancel."""

    @abc.abstractmethod
    def list_all_requests(self, *, status: str | None = None,
                          limit: int = 50, offset: int = 0) -> list[PrivacyAction]:
        """Admin-wide view across every founder's requests -- unlike
        list_requests, not scoped to one founder_id. Backs the admin panel's
        review queue."""

    @abc.abstractmethod
    def resolve_request(self, request_id: int, *, status: str, processed_by: str,
                        processing_notes: str | None, rejection_reason: str | None,
                        at: datetime) -> PrivacyAction:
        """Admin fulfilment: move a queued request (view_data, correct_data,
        or any other logged action) to in_progress/completed/rejected. This is
        the piece that was missing entirely before -- without it, every
        "Request" button in the Privacy Center created a row that stayed
        'pending' forever, with no code path anywhere that could resolve it."""


class InMemoryPrivacyRepository(PrivacyRepository):
    """Offline double. `seed_export` lets tests define what the export should contain
    without needing any of the 100+ production tables."""

    def __init__(self, export_sections: dict | None = None) -> None:
        self._export = export_sections or {}
        self._states: dict[int, PrivacyState] = {}
        self._requests: list[PrivacyAction] = []
        self._next_id = 1
        self._lock = threading.RLock()

    def seed_export(self, sections: dict) -> None:
        with self._lock:
            self._export = sections

    def gather_export(self, founder_id: int, generated_at: datetime) -> ExportBundle:
        with self._lock:
            return ExportBundle(founder_id=founder_id, generated_at=generated_at,
                                sections=dict(self._export))

    def get_state(self, founder_id: int) -> PrivacyState:
        with self._lock:
            return self._states.get(founder_id) or PrivacyState(
                founder_id=founder_id, processing_restricted=False,
                processing_restricted_at=None, deletion_requested_at=None,
                deletion_scheduled_at=None)

    def set_restriction(self, founder_id: int, *, restricted: bool, at: datetime) -> PrivacyState:
        with self._lock:
            current = self.get_state(founder_id)
            state = PrivacyState(
                founder_id=founder_id,
                processing_restricted=restricted,
                processing_restricted_at=at if restricted else None,
                deletion_requested_at=current.deletion_requested_at,
                deletion_scheduled_at=current.deletion_scheduled_at,
                deletion_executed_at=current.deletion_executed_at)
            self._states[founder_id] = state
            return state

    def schedule_deletion(self, founder_id: int, *, requested_at: datetime,
                          scheduled_at: datetime) -> PrivacyState:
        with self._lock:
            current = self.get_state(founder_id)
            state = PrivacyState(
                founder_id=founder_id,
                processing_restricted=current.processing_restricted,
                processing_restricted_at=current.processing_restricted_at,
                deletion_requested_at=requested_at,
                deletion_scheduled_at=scheduled_at)
            self._states[founder_id] = state
            return state

    def log_request(self, founder_id: int, *, request_type: str, details: str | None,
                    at: datetime, due_by: datetime | None) -> PrivacyAction:
        with self._lock:
            action = PrivacyAction(request_id=self._next_id, founder_id=founder_id,
                                   request_type=request_type, status="pending",
                                   requested_at=at, due_by=due_by)
            self._next_id += 1
            self._requests.append(action)
            return action

    def list_requests(self, founder_id: int) -> list[PrivacyAction]:
        with self._lock:
            return [r for r in reversed(self._requests) if r.founder_id == founder_id]

    def find_due_for_deletion(self, now: datetime) -> list[int]:
        with self._lock:
            return sorted(
                fid for fid, s in self._states.items()
                if s.deletion_scheduled_at is not None
                and s.deletion_scheduled_at <= now
                and s.deletion_executed_at is None
            )

    def cancel_deletion(self, founder_id: int) -> PrivacyState:
        with self._lock:
            current = self.get_state(founder_id)
            if not current.deletion_pending:
                raise NoDeletionToCancelError(founder_id)
            state = PrivacyState(
                founder_id=founder_id,
                processing_restricted=current.processing_restricted,
                processing_restricted_at=current.processing_restricted_at,
                deletion_requested_at=None,
                deletion_scheduled_at=None,
                deletion_executed_at=None,
            )
            self._states[founder_id] = state
            return state

    def list_all_requests(self, *, status: str | None = None,
                          limit: int = 50, offset: int = 0) -> list[PrivacyAction]:
        with self._lock:
            items = [r for r in reversed(self._requests) if status is None or r.status == status]
        return items[offset:offset + limit]

    def resolve_request(self, request_id: int, *, status: str, processed_by: str,
                        processing_notes: str | None, rejection_reason: str | None,
                        at: datetime) -> PrivacyAction:
        with self._lock:
            for i, r in enumerate(self._requests):
                if r.request_id == request_id:
                    updated = replace(
                        r, status=status, processed_by=processed_by,
                        processing_notes=processing_notes, rejection_reason=rejection_reason,
                        completed_at=at if status in ("completed", "rejected") else r.completed_at,
                    )
                    self._requests[i] = updated
                    return updated
            raise PrivacyRequestNotFoundError(request_id)
