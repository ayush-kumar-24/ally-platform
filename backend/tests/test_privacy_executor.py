"""Hermetic tests for the deletion executor and the cancel flow (in-memory doubles,
no DB). Mirrors the SQL implementation's contract closely enough that a behaviour
change here should also be made in app/privacy/db_repository.py."""

from datetime import datetime, timedelta, timezone

from app.privacy.deletion_repository import InMemoryDeletionRepository
from app.privacy.errors import NoDeletionPendingError
from app.privacy.executor import DeletionExecutor
from app.privacy.repository import InMemoryPrivacyRepository
from app.privacy.service import build_privacy_service

T0 = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)
PAST_DUE = T0 - timedelta(days=1)
NOT_YET_DUE = T0 + timedelta(days=5)


# --- executor: run_due --------------------------------------------------------


def test_run_due_erases_only_founders_past_grace():
    repo = InMemoryDeletionRepository()
    due_id = repo.schedule(1, requested_at=T0 - timedelta(days=31), grace_period_ends_at=PAST_DUE)
    not_due_id = repo.schedule(2, requested_at=T0, grace_period_ends_at=NOT_YET_DUE)
    executor = DeletionExecutor(repo, clock=lambda: T0)

    summary = executor.run_due()

    assert summary.checked == 1
    assert summary.succeeded_count == 1 and summary.failed_count == 0
    assert repo.status_for(1) == "completed"
    assert repo.status_for(2) == "grace_period"          # untouched -- not due yet
    assert 1 in repo.purge_calls()
    assert 2 not in repo.purge_calls()
    _ = due_id, not_due_id


def test_run_due_is_idempotent_across_sweeps():
    repo = InMemoryDeletionRepository()
    repo.schedule(1, requested_at=T0, grace_period_ends_at=PAST_DUE)
    executor = DeletionExecutor(repo, clock=lambda: T0)

    first = executor.run_due()
    second = executor.run_due()

    assert first.succeeded_count == 1
    assert second.checked == 0                            # already completed, not re-picked up
    assert len(repo.purge_calls()) == 1


def test_run_due_skips_cancelled_requests():
    repo = InMemoryDeletionRepository()
    repo.schedule(1, requested_at=T0, grace_period_ends_at=PAST_DUE)
    repo.cancel(1)
    executor = DeletionExecutor(repo, clock=lambda: T0)

    summary = executor.run_due()

    assert summary.checked == 0
    assert 1 not in repo.purge_calls()


def test_run_due_isolates_one_failure_from_the_rest():
    class FlakyRepo(InMemoryDeletionRepository):
        def purge_founder(self, founder_id, *, at):
            if founder_id == 1:
                raise RuntimeError("simulated FK violation")
            return super().purge_founder(founder_id, at=at)

    repo = FlakyRepo()
    repo.schedule(1, requested_at=T0, grace_period_ends_at=PAST_DUE)
    repo.schedule(2, requested_at=T0, grace_period_ends_at=PAST_DUE)
    executor = DeletionExecutor(repo, clock=lambda: T0)

    summary = executor.run_due()

    assert summary.succeeded_count == 1 and summary.failed_count == 1
    assert summary.failed[0].founder_id == 1
    # The failed row reverts to grace_period rather than getting stuck -- the next
    # sweep will retry it.
    assert repo.status_for(1) == "grace_period"
    assert repo.status_for(2) == "completed"


def test_run_due_respects_batch_size():
    repo = InMemoryDeletionRepository()
    for fid in range(5):
        repo.schedule(fid, requested_at=T0, grace_period_ends_at=PAST_DUE)
    executor = DeletionExecutor(repo, clock=lambda: T0)

    summary = executor.run_due(batch_size=2)

    assert summary.checked == 2


# --- executor: execute_now (Auth webhook path) --------------------------------


def test_execute_now_bypasses_the_grace_window():
    repo = InMemoryDeletionRepository()
    executor = DeletionExecutor(repo, clock=lambda: T0)

    outcome = executor.execute_now(7)

    assert outcome.succeeded
    assert repo.status_for(7) == "completed"
    assert 7 in repo.purge_calls()


def test_execute_now_reuses_an_existing_pending_request():
    repo = InMemoryDeletionRepository()
    deletion_id = repo.schedule(7, requested_at=T0, grace_period_ends_at=NOT_YET_DUE)
    executor = DeletionExecutor(repo, clock=lambda: T0)

    outcome = executor.execute_now(7)

    assert outcome.succeeded and outcome.deletion_id == deletion_id
    assert repo.status_for(7) == "completed"


# --- cancel (PrivacyService, in-memory repository) -----------------------------


def test_cancel_account_deletion_clears_pending_state():
    repo = InMemoryPrivacyRepository()
    service = build_privacy_service(repo, clock=lambda: T0)
    service.request_account_deletion(1)

    state, action = service.cancel_account_deletion(1)

    assert state.deletion_pending is False
    assert state.deletion_scheduled_at is None
    assert action.request_type == "withdraw_consent"


def test_cancel_account_deletion_without_a_pending_request_raises():
    repo = InMemoryPrivacyRepository()
    service = build_privacy_service(repo, clock=lambda: T0)

    try:
        service.cancel_account_deletion(1)
        assert False, "expected NoDeletionPendingError"
    except NoDeletionPendingError as exc:
        assert exc.status_code == 409


def test_cancel_then_re_request_works():
    """A founder who cancels can change their mind again later -- cancelling must
    not leave a stale 'already requested' state behind."""
    repo = InMemoryPrivacyRepository()
    service = build_privacy_service(repo, clock=lambda: T0)
    service.request_account_deletion(1)
    service.cancel_account_deletion(1)

    state, _ = service.request_account_deletion(1)

    assert state.deletion_pending is True
