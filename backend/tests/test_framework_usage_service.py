"""Domain tests for the Framework Usage module. In-memory, deterministic, offline."""

from datetime import datetime, timedelta, timezone

import pytest

from app.framework_usage import (
    InMemoryFrameworkUsageRepository,
    InvalidFrameworkUsageInputError,
    build_framework_usage_service,
)

T0 = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)


class StepClock:
    def __init__(self, start=T0, step=timedelta(seconds=1)):
        self._now, self._step = start, step

    def __call__(self):
        v = self._now
        self._now += self._step
        return v


def svc():
    return build_framework_usage_service(InMemoryFrameworkUsageRepository(), clock=StepClock())


# --- record_used ------------------------------------------------------


def test_list_usage_empty_for_new_founder():
    assert svc().list_usage(1) == ()


def test_record_used_creates_entry():
    s = svc()
    u = s.record_used(1, "first-principles")
    assert u.founder_id == 1
    assert u.framework_id == "first-principles"
    assert u.last_used_at == T0
    assert u.note == ""


def test_record_used_appears_in_list():
    s = svc()
    s.record_used(1, "first-principles")
    items = s.list_usage(1)
    assert len(items) == 1 and items[0].framework_id == "first-principles"


def test_record_used_again_bumps_timestamp_keeps_note():
    s = svc()
    s.record_used(1, "swot")
    s.save_note(1, "swot", "Used on the pricing pivot.")
    second = s.record_used(1, "swot")
    assert second.last_used_at == datetime(2026, 8, 20, 12, 0, 1, tzinfo=timezone.utc)
    assert second.note == "Used on the pricing pivot."


def test_record_used_empty_framework_id_rejected():
    with pytest.raises(InvalidFrameworkUsageInputError):
        svc().record_used(1, "   ")


def test_record_used_overlong_framework_id_rejected():
    with pytest.raises(InvalidFrameworkUsageInputError):
        svc().record_used(1, "x" * 65)


def test_founder_isolation():
    s = svc()
    s.record_used(1, "first-principles")
    assert s.list_usage(2) == ()


def test_multiple_frameworks_newest_first():
    s = svc()
    s.record_used(1, "first-principles")
    s.record_used(1, "swot")
    items = s.list_usage(1)
    assert [i.framework_id for i in items] == ["swot", "first-principles"]


# --- save_note ----------------------------------------------------------


def test_save_note_after_record_used():
    s = svc()
    s.record_used(1, "okrs")
    updated = s.save_note(1, "okrs", "Set quarterly OKRs with the team.")
    assert updated.note == "Set quarterly OKRs with the team."
    assert updated.last_used_at == T0  # untouched by the note save


def test_save_note_without_prior_record_used_still_creates_entry():
    """Edge case the frontend shouldn't hit (it always opens the detail page
    first), but the service handles it gracefully rather than 404ing."""
    s = svc()
    updated = s.save_note(1, "ikigai", "A note with no prior visit.")
    assert updated.note == "A note with no prior visit."
    assert updated.last_used_at == T0


def test_save_note_blank_clears_it():
    s = svc()
    s.record_used(1, "okrs")
    s.save_note(1, "okrs", "a note")
    cleared = s.save_note(1, "okrs", "   ")
    assert cleared.note == ""


def test_save_note_is_trimmed():
    s = svc()
    s.record_used(1, "okrs")
    updated = s.save_note(1, "okrs", "  spaced  ")
    assert updated.note == "spaced"


def test_save_note_overlong_rejected():
    s = svc()
    s.record_used(1, "okrs")
    with pytest.raises(InvalidFrameworkUsageInputError):
        s.save_note(1, "okrs", "x" * 2001)


def test_save_note_founder_isolation():
    s = svc()
    s.record_used(1, "okrs")
    s.save_note(1, "okrs", "founder 1's note")
    assert s.list_usage(2) == ()


# --- determinism --------------------------------------------------------


def test_deterministic_execution():
    def run():
        s = svc()
        s.record_used(1, "first-principles")
        s.save_note(1, "first-principles", "a")
        return s.list_usage(1)[0].last_used_at
    assert run() == run()
