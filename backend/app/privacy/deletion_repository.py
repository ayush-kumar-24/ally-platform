"""Persistence seam for the deletion EXECUTOR -- distinct from `PrivacyRepository`.

`PrivacyRepository` is scoped to one founder at a time (it answers "what is this
founder's privacy standing"). The executor's question is different in shape: "which
founders are due right now, across the whole table", and once it has one, "erase
everything about this founder". Folding that into `PrivacyRepository` would make
every other privacy read implicitly capable of a cross-founder scan; keeping it
separate means the two capabilities are granted to different callers.

Two implementations, the same pattern as the rest of this module:
  * InMemoryDeletionRepository -- deterministic, used by the hermetic executor tests.
  * SqlAlchemyDeletionRepository (db_repository.py) -- the production store.
"""

from __future__ import annotations

import abc
import threading
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class DueDeletion:
    """One founder whose grace period has elapsed and who is due for erasure."""

    deletion_id: int
    founder_id: int
    requested_at: datetime
    grace_period_ends_at: datetime


@dataclass(frozen=True)
class DeletionOutcome:
    """What actually happened when one founder's erasure was executed."""

    founder_id: int
    deletion_id: int
    data_types_deleted: dict = field(default_factory=dict)
    completed_at: datetime | None = None
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.error is None


class DeletionRepository(abc.ABC):
    @abc.abstractmethod
    def list_due(self, *, now: datetime, limit: int) -> list[DueDeletion]:
        """Founders past their grace period whose erasure has not yet run (or
        completed/cancelled). Ordered oldest-due-first so a backlog drains fairly."""

    @abc.abstractmethod
    def ensure_immediate(self, founder_id: int, *, at: datetime) -> int:
        """Create (or revive) the founder's tracking row as due right now.

        Used by the Supabase Auth webhook: once the auth account itself is gone
        there is no login left to recover via a grace window, so that founder's
        data erasure has nothing left to wait for. Returns the deletion_id so the
        caller can run it through the same execute path as a scheduled sweep."""

    @abc.abstractmethod
    def mark_processing(self, deletion_id: int) -> None:
        """Claim a row before acting on it, so a sweep that overlaps a previous
        one (retry, two instances) does not erase the same founder twice."""

    @abc.abstractmethod
    def purge_founder(self, founder_id: int, *, at: datetime) -> dict:
        """Erase/anonymise everything the founder's Art 17 request covers.
        Returns a {table: rows_affected | "anonymised"} summary for the record."""

    @abc.abstractmethod
    def mark_completed(self, deletion_id: int, *, at: datetime, data_types_deleted: dict) -> None: ...

    @abc.abstractmethod
    def mark_failed(self, deletion_id: int, *, reason: str) -> None:
        """Revert a claimed row to grace_period so the next sweep retries it,
        rather than leaving it stuck in `processing` forever."""


class InMemoryDeletionRepository(DeletionRepository):
    """Test double. Seed via `schedule` (mirrors what schedule_deletion writes in
    the real repository); `purge_calls` and `state_for` let tests assert on effect."""

    def __init__(self) -> None:
        self._rows: dict[int, dict] = {}
        self._next_id = 1
        self._purged: dict[int, dict] = {}
        self._lock = threading.RLock()

    def schedule(self, founder_id: int, *, requested_at: datetime,
                 grace_period_ends_at: datetime, status: str = "grace_period") -> int:
        with self._lock:
            deletion_id = self._next_id
            self._next_id += 1
            self._rows[deletion_id] = {
                "deletion_id": deletion_id, "founder_id": founder_id,
                "requested_at": requested_at, "grace_period_ends_at": grace_period_ends_at,
                "status": status, "completed_at": None, "data_types_deleted": {},
            }
            return deletion_id

    def cancel(self, founder_id: int) -> None:
        with self._lock:
            for row in self._rows.values():
                if row["founder_id"] == founder_id and row["status"] in ("pending_otp", "grace_period"):
                    row["status"] = "cancelled"

    def status_for(self, founder_id: int) -> str | None:
        with self._lock:
            for row in self._rows.values():
                if row["founder_id"] == founder_id:
                    return row["status"]
        return None

    def purge_calls(self) -> dict[int, dict]:
        """Test helper: founder_id -> the dict purge_founder returned for it."""
        return dict(self._purged)

    # --- DeletionRepository ------------------------------------------------

    def list_due(self, *, now: datetime, limit: int) -> list[DueDeletion]:
        with self._lock:
            due = [row for row in self._rows.values()
                   if row["status"] == "grace_period" and row["grace_period_ends_at"] <= now]
        due.sort(key=lambda r: r["grace_period_ends_at"])
        return [DueDeletion(deletion_id=r["deletion_id"], founder_id=r["founder_id"],
                            requested_at=r["requested_at"],
                            grace_period_ends_at=r["grace_period_ends_at"])
                for r in due[:limit]]

    def ensure_immediate(self, founder_id: int, *, at: datetime) -> int:
        with self._lock:
            for row in self._rows.values():
                if row["founder_id"] == founder_id and row["status"] in ("pending_otp", "grace_period"):
                    row["grace_period_ends_at"] = at
                    return row["deletion_id"]
        return self.schedule(founder_id, requested_at=at, grace_period_ends_at=at)

    def mark_processing(self, deletion_id: int) -> None:
        with self._lock:
            self._rows[deletion_id]["status"] = "processing"

    def purge_founder(self, founder_id: int, *, at: datetime) -> dict:
        summary = {"conversations": "deleted", "sessions": "deleted", "founder_profile": "anonymised"}
        with self._lock:
            self._purged[founder_id] = summary
        return summary

    def mark_completed(self, deletion_id: int, *, at: datetime, data_types_deleted: dict) -> None:
        with self._lock:
            row = self._rows[deletion_id]
            row["status"] = "completed"
            row["completed_at"] = at
            row["data_types_deleted"] = data_types_deleted

    def mark_failed(self, deletion_id: int, *, reason: str) -> None:
        with self._lock:
            row = self._rows[deletion_id]
            row["status"] = "grace_period"
            row["last_error"] = reason
