"""DeletionExecutor -- the piece that actually carries out a scheduled erasure.

`PrivacyService.request_account_deletion` only ever *schedules* one (see its
docstring for why: no single HTTP call should irreversibly destroy an account).
Something still has to run once the 30-day grace window has passed and turn the
schedule into a real erasure. That is this class.

Deliberately NOT a hard `DELETE FROM founders` for the founder row itself: dozens of
tables reference `founder_id` and most are NOT `ON DELETE CASCADE` (subscriptions,
payments, privacy_requests, report_shares, data_deletion_requests itself -- the audit
trail an erasure needs to prove it happened). A hard delete of the parent row would
either violate those foreign keys or silently cascade compliance records away.
Erasure here means: delete the founder's PII-bearing activity data outright, and
anonymise the founders row in place so it can no longer identify them while the
tables that must legally persist (billing, the audit trail) keep a row to point at.

Per-founder isolation, same reasoning as AdminPanelService.bulk_adjust_credits: one
founder's erasure failing (a stray FK, a locked row) must not abort the whole sweep
and must not leave that founder half-erased -- the row reverts to `grace_period` so
the next sweep retries it, exactly like a pending job that failed once.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from app.privacy.deletion_repository import DeletionOutcome, DeletionRepository

DEFAULT_BATCH_SIZE = 50


@dataclass(frozen=True)
class ExecutionSummary:
    """What one sweep did, for the webhook response / ops log."""

    checked: int
    succeeded: list[DeletionOutcome] = field(default_factory=list)
    failed: list[DeletionOutcome] = field(default_factory=list)

    @property
    def succeeded_count(self) -> int:
        return len(self.succeeded)

    @property
    def failed_count(self) -> int:
        return len(self.failed)


class DeletionExecutor:
    def __init__(self, repository: DeletionRepository, *,
                 clock: Callable[[], datetime] | None = None):
        self.repository = repository
        self._now = clock or (lambda: datetime.now(timezone.utc))

    def run_due(self, *, batch_size: int = DEFAULT_BATCH_SIZE) -> ExecutionSummary:
        """Erase every founder whose grace period has elapsed, up to `batch_size`.

        Bounded rather than unbounded on purpose: an outage that lets a backlog
        build up should drain over a few sweeps, not turn one sweep into a
        multi-hour transaction that blocks the next scheduled run from starting.
        """
        now = self._now()
        due = self.repository.list_due(now=now, limit=batch_size)
        succeeded: list[DeletionOutcome] = []
        failed: list[DeletionOutcome] = []
        for item in due:
            outcome = self._execute_one(item.deletion_id, item.founder_id, at=now)
            (succeeded if outcome.succeeded else failed).append(outcome)
        return ExecutionSummary(checked=len(due), succeeded=succeeded, failed=failed)

    def execute_now(self, founder_id: int) -> DeletionOutcome:
        """Erase one founder immediately, bypassing the grace window.

        For the Supabase Auth deletion webhook only: once the auth account is gone
        there is nothing a grace period would let the founder recover, so waiting
        30 days only prolongs holding data for someone who can no longer log in to
        ask for it back.
        """
        now = self._now()
        deletion_id = self.repository.ensure_immediate(founder_id, at=now)
        return self._execute_one(deletion_id, founder_id, at=now)

    def _execute_one(self, deletion_id: int, founder_id: int, *, at: datetime) -> DeletionOutcome:
        self.repository.mark_processing(deletion_id)
        try:
            data_types_deleted = self.repository.purge_founder(founder_id, at=at)
        except Exception as exc:                                    # noqa: BLE001 - reported, not hidden
            self.repository.mark_failed(deletion_id, reason=str(exc))
            return DeletionOutcome(founder_id=founder_id, deletion_id=deletion_id, error=str(exc))

        self.repository.mark_completed(deletion_id, at=at, data_types_deleted=data_types_deleted)
        return DeletionOutcome(founder_id=founder_id, deletion_id=deletion_id,
                               data_types_deleted=data_types_deleted, completed_at=at)
