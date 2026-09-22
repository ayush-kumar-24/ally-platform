"""Domain tests for the Consents module. In-memory, deterministic, offline."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from itertools import count

import pytest

from app.consents.defaults import CURRENT_PRIVACY_VERSION, CURRENT_TERMS_VERSION
from app.consents import (
    InvalidConsentInputError,
    TermsNotAcceptedError,
    build_consent_service,
)

T0 = datetime(2026, 8, 2, 12, 0, 0, tzinfo=timezone.utc)
# The CURRENT versions, from the constants -- see the note in
# test_api_consents.py. Tests that need a STALE version still spell one out.
V = {"terms_version": CURRENT_TERMS_VERSION, "privacy_version": CURRENT_PRIVACY_VERSION}


class StepClock:
    def __init__(self, start=T0, step=timedelta(seconds=1)):
        self._now, self._step = start, step

    def __call__(self):
        v = self._now
        self._now += self._step
        return v


def svc():
    c = count(1)
    return build_consent_service(clock=StepClock(), id_factory=lambda: f"c-{next(c)}")


# --- recording --------------------------------------------------------------


def test_record_consent_stores_all_fields():
    s = svc()
    record, created = s.record_consent(1, agree_terms=True, agree_diagnosis=True, **V)
    assert created is True
    assert record.founder_id == 1
    assert record.terms_version == CURRENT_TERMS_VERSION and record.privacy_version == CURRENT_PRIVACY_VERSION
    assert record.agree_terms is True and record.agree_diagnosis is True
    assert record.consented_at == T0


def test_diagnosis_consent_defaults_to_false():
    """An omitted optional opt-in must never be read as consent."""
    record, _ = svc().record_consent(1, agree_terms=True, **V)
    assert record.agree_diagnosis is False


def test_terms_must_be_accepted():
    with pytest.raises(TermsNotAcceptedError):
        svc().record_consent(1, agree_terms=False, **V)


def test_refused_consent_is_not_stored():
    s = svc()
    with pytest.raises(TermsNotAcceptedError):
        s.record_consent(1, agree_terms=False, **V)
    assert s.get_current(1) is None and s.list_history(1) == []


@pytest.mark.parametrize("bad", ["", "   ", "latest", "v1.0", "1.0.0.0", "x" * 21])
def test_invalid_version_rejected(bad):
    with pytest.raises(InvalidConsentInputError):
        svc().record_consent(1, agree_terms=True, terms_version=bad, privacy_version="1.0")


def test_version_is_trimmed():
    record, _ = svc().record_consent(1, agree_terms=True, terms_version=" 1.0 ", privacy_version="2.1")
    assert record.terms_version == "1.0" and record.privacy_version == "2.1"


# --- idempotency / duplicate submissions ------------------------------------


def test_identical_repost_is_idempotent():
    s = svc()
    first, created_1 = s.record_consent(1, agree_terms=True, agree_diagnosis=True, **V)
    second, created_2 = s.record_consent(1, agree_terms=True, agree_diagnosis=True, **V)
    assert created_1 is True and created_2 is False
    assert second.consent_id == first.consent_id
    assert len(s.list_history(1)) == 1          # nothing appended


def test_changed_consent_is_appended_not_replaced():
    s = svc()
    s.record_consent(1, agree_terms=True, agree_diagnosis=True, **V)
    changed, created = s.record_consent(1, agree_terms=True, agree_diagnosis=False, **V)
    assert created is True and changed.agree_diagnosis is False
    history = s.list_history(1)
    assert len(history) == 2                     # the original survives as evidence
    assert history[0].agree_diagnosis is False   # newest first
    assert history[1].agree_diagnosis is True


def test_new_document_version_is_appended():
    s = svc()
    s.record_consent(1, agree_terms=True, terms_version="1.0", privacy_version="1.0")
    _, created = s.record_consent(1, agree_terms=True, terms_version="2.0", privacy_version="1.0")
    assert created is True and len(s.list_history(1)) == 2


# --- reads ------------------------------------------------------------------


def test_get_current_returns_newest():
    s = svc()
    s.record_consent(1, agree_terms=True, agree_diagnosis=True, **V)
    s.record_consent(1, agree_terms=True, agree_diagnosis=False, **V)
    assert s.get_current(1).agree_diagnosis is False


def test_no_consent_reads_as_absent():
    s = svc()
    assert s.get_current(1) is None
    assert s.has_consented(1) is False
    assert s.list_history(1) == []


def test_may_process_diagnosis_data_fails_closed():
    s = svc()
    assert s.may_process_diagnosis_data(1) is False        # no record at all
    s.record_consent(1, agree_terms=True, agree_diagnosis=False, **V)
    assert s.may_process_diagnosis_data(1) is False        # opted out
    s.record_consent(1, agree_terms=True, agree_diagnosis=True, **V)
    assert s.may_process_diagnosis_data(1) is True


def test_needs_reconsent_on_missing_or_superseded_version():
    s = svc()
    assert s.needs_reconsent(1) is True                    # never consented
    s.record_consent(1, agree_terms=True, terms_version="0.9",
                     privacy_version=CURRENT_PRIVACY_VERSION)
    assert s.needs_reconsent(1) is True                    # stale terms
    s.record_consent(1, agree_terms=True, **V)
    assert s.needs_reconsent(1) is False


# --- isolation / concurrency / determinism ----------------------------------


def test_founder_isolation():
    s = svc()
    s.record_consent(1, agree_terms=True, agree_diagnosis=True, **V)
    assert s.get_current(2) is None
    assert s.list_history(2) == []
    assert s.may_process_diagnosis_data(2) is False


def test_concurrent_reads():
    s = svc()
    s.record_consent(1, agree_terms=True, **V)

    def read(_):
        return s.get_current(1) is not None

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert all(pool.map(read, range(40)))


def test_deterministic_execution():
    def run():
        s = svc()
        s.record_consent(1, agree_terms=True, agree_diagnosis=True, **V)
        s.record_consent(1, agree_terms=True, agree_diagnosis=False, **V)
        return s.list_history(1)
    assert run() == run()


# --- where the consent came from -------------------------------------------
#
# The ledger's job is to DEMONSTRATE consent, not assert it: what was agreed,
# to which version, when, and now from where.

def test_the_address_is_stored_with_the_consent():
    s = svc()
    record, created = s.record_consent(7, **V, agree_terms=True, ip_address="49.36.1.2")
    assert created and record.ip_address == "49.36.1.2"


def test_a_consent_without_an_address_records_none_not_a_placeholder():
    """"Not recorded" and "recorded as unknown" are different claims, and only
    the first is true when no address could be resolved."""
    s = svc()
    record, _ = s.record_consent(7, **V, agree_terms=True)
    assert record.ip_address is None


def test_the_same_decision_from_a_new_address_does_not_append_a_record():
    """The ledger records DECISIONS. Re-opening the app on mobile data is not a
    new decision, and comparing the address would append a duplicate every time
    a founder's network changed -- the exact pollution the idempotency check
    exists to prevent."""
    s = svc()
    first, created = s.record_consent(7, **V, agree_terms=True, ip_address="49.36.1.2")
    again, created_again = s.record_consent(7, **V, agree_terms=True, ip_address="203.0.113.9")

    assert created is True and created_again is False
    # The original record comes back untouched, address included.
    assert again.consent_id == first.consent_id
    assert again.ip_address == "49.36.1.2"
    assert len(s.list_history(7)) == 1


def test_a_real_change_of_mind_records_the_address_it_came_from():
    s = svc()
    s.record_consent(7, **V, agree_terms=True, agree_diagnosis=False, ip_address="49.36.1.2")
    changed, created = s.record_consent(
        7, **V, agree_terms=True, agree_diagnosis=True, ip_address="203.0.113.9")

    assert created is True
    assert changed.ip_address == "203.0.113.9"
    assert len(s.list_history(7)) == 2
