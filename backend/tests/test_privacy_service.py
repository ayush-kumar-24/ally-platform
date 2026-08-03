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
    assert action.request_type == "portability" and action.status == "pending"


def test_export_is_immediate_no_due_date():
    """Served now, so there is nothing to wait for."""
    _, action = svc().export_data(1)
    assert action.due_by is None


def test_export_is_logged_for_accountability():
    s = svc()
    s.export_data(1)
    assert [r.request_type for r in s.list_requests(1)] == ["portability"]


# --- Art 17: erasure --------------------------------------------------------


def test_deletion_is_scheduled_not_immediate():
    s = svc()
    state, action = s.request_account_deletion(1)
    assert state.deletion_requested_at == T0
    assert state.deletion_scheduled_at == T0 + timedelta(days=DELETION_GRACE_DAYS)
    assert state.deletion_pending is True
    assert action.request_type == "withdraw_consent"


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
