"""Privacy persistence seam.

`PrivacyRepository` is the interface the service depends on. Two implementations:
  * InMemoryPrivacyRepository -- deterministic, thread-safe, offline (used by tests).
  * SqlAlchemyPrivacyRepository (db_repository.py) -- the production store.
Swapping one for the other is a repository replacement only; the service is unchanged.
"""

from __future__ import annotations

import abc
import threading
from datetime import datetime

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
                deletion_scheduled_at=current.deletion_scheduled_at)
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
