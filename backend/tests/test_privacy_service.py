"""Domain tests for the Privacy Center. In-memory, deterministic, offline."""

from datetime import datetime, timedelta, timezone

import pytest

from app.consents import build_consent_service
from app.privacy import (
    DELETION_GRACE_DAYS,
    DeletionAlreadyRequestedError,
    InMemoryPrivacyRepository,
    build_privacy_service,
)

T0 = datetime(2026, 8, 2, 12, 0, 0, tzinfo=timezone.utc)


def svc(consent_service=None, sections=None):
    repo = InMemoryPrivacyRepository(sections or {"founder_profile": [{"founder_id": 1}]})
    return build_privacy_service(repo, clock=lambda: T0, consent_service=consent_service)


# --- Art 15 + 20: export ----------------------------------------------------


def test_export_returns_sections_and_logs_request():
    s = svc(sections={"founder_profile": [{"founder_id": 1}], "plans": [{"a": 1}, {"b": 2}]})
    bundle, action = s.export_data(1)
    assert bundle.founder_id == 1 and bundle.generated_at == T0
    assert set(bundle.sections) == {"founder_profile", "plans"}
    assert bundle.record_count == 3
    # A bare export_data() is the right of ACCESS, and is logged as such. It used
    # to log "portability" whichever button the founder pressed, so the audit
    # trail could not tell the two rights apart.
    assert action.request_type == "download_data" and action.status == "pending"


def test_portability_export_is_logged_as_portability():
    """The other button exercises Art 20, and the audit trail says so."""
    s = svc()
    _, action = s.export_data(1, kind="portability")
    assert action.request_type == "portability"


def test_unknown_export_kind_falls_back_to_access():
    """Fails closed towards the fuller export: a typo must not silently hand
    back a narrower file than the founder asked for."""
    _, action = svc().export_data(1, kind="nonsense")
    assert action.request_type == "download_data"


def test_export_is_immediate_no_due_date():
    """Served now, so there is nothing to wait for."""
    _, action = svc().export_data(1)
    assert action.due_by is None


def test_export_is_logged_for_accountability():
    s = svc()
    s.export_data(1)
    assert [r.request_type for r in s.list_requests(1)] == ["download_data"]


# --- Art 17: erasure --------------------------------------------------------


def test_deletion_is_scheduled_not_immediate():
    s = svc()
    state, action = s.request_account_deletion(1)
    assert state.deletion_requested_at == T0
    assert state.deletion_scheduled_at == T0 + timedelta(days=DELETION_GRACE_DAYS)
    assert state.deletion_pending is True
    # Erasure has its own label (f2c7a91d4e83). It used to log "withdraw_consent",
    # the same value cancellation and actual consent withdrawal wrote, so the audit
    # trail could not tell a deletion request from either of them.
    assert action.request_type == "delete_account"


def test_second_deletion_request_refused():
    """Otherwise a repeated call could push the date back forever."""
    s = svc()
    s.request_account_deletion(1)
    with pytest.raises(DeletionAlreadyRequestedError):
        s.request_account_deletion(1)


def test_deletion_blocks_processing():
    s = svc()
    assert s.may_process(1) is True
    s.request_account_deletion(1)
    assert s.may_process(1) is False


# --- Art 7(3): withdrawal ---------------------------------------------------


def test_withdraw_pauses_processing_without_deleting():
    s = svc()
    state, action = s.withdraw_consent(1)
    assert state.processing_restricted is True
    assert state.deletion_pending is False        # withdrawal is not erasure
    assert action.request_type == "withdraw_consent"


def test_withdraw_writes_to_the_consent_ledger():
    consents = build_consent_service(clock=lambda: T0)
    consents.record_consent(1, terms_version="1.0", privacy_version="1.0",
                            agree_terms=True, agree_diagnosis=True)
    s = svc(consent_service=consents)
    s.withdraw_consent(1)
    assert consents.get_current(1).agree_diagnosis is False
    assert consents.may_process_diagnosis_data(1) is False
    assert len(consents.list_history(1)) == 2      # original grant preserved


def test_withdraw_without_prior_consent_is_safe():
    consents = build_consent_service(clock=lambda: T0)
    s = svc(consent_service=consents)
    state, _ = s.withdraw_consent(1)
    assert state.processing_restricted is True
    assert consents.get_current(1) is None         # nothing invented


# --- Art 18: restriction ----------------------------------------------------


def test_restrict_and_lift():
    s = svc()
    state, _ = s.restrict_processing(1, restricted=True)
    assert state.processing_restricted is True and state.processing_restricted_at == T0
    assert s.may_process(1) is False

    lifted, _ = s.restrict_processing(1, restricted=False)
    assert lifted.processing_restricted is False and lifted.processing_restricted_at is None
    assert s.may_process(1) is True


def test_restriction_does_not_touch_deletion_state():
    s = svc()
    s.request_account_deletion(1)
    state, _ = s.restrict_processing(1, restricted=True)
    assert state.deletion_pending is True          # preserved


def test_every_action_is_logged():
    s = svc()
    s.export_data(1)
    s.restrict_processing(1, restricted=True)
    s.request_account_deletion(1)
    assert len(s.list_requests(1)) == 3


# --- isolation --------------------------------------------------------------


def test_founder_isolation():
    s = svc()
    s.restrict_processing(1, restricted=True)
    assert s.get_state(2).processing_restricted is False
    assert s.list_requests(2) == []
    assert s.may_process(2) is True

def test_cancelled_deletion_is_logged_as_its_own_event():
    """Erasure, cancelling erasure and withdrawing consent are three different
    things a founder can do. Before f2c7a91d4e83 all three logged the same
    label, so "prove this founder cancelled" was unanswerable from the table
    that exists to answer exactly that."""
    s = svc()
    s.request_account_deletion(1)
    _, action = s.cancel_account_deletion(1)
    assert action.request_type == "cancel_deletion"
    # Newest first, so the cancellation leads and the request it undid follows.
    assert [r.request_type for r in s.list_requests(1)] == [
        "cancel_deletion", "delete_account",
    ]
