"""Domain tests for the Settings module (Phase 11). In-memory repo, deterministic."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from app.settings import (
    DEFAULT_REMINDER_TIME,
    DEFAULT_SESSION_TIMEOUT_MINUTES,
    InMemorySettingsRepository,
    InvalidSettingError,
    SettingsService,
    build_settings_service,
)

T0 = datetime(2026, 7, 29, 9, 0, 0, tzinfo=timezone.utc)


class StepClock:
    def __init__(self, start=T0, step=timedelta(seconds=1)):
        self._now, self._step = start, step

    def __call__(self):
        v = self._now
        self._now += self._step
        return v


def svc(repo=None):
    return build_settings_service(repo, now=StepClock())


# --- defaults + load --------------------------------------------------------


def test_get_creates_defaults_on_first_access():
    s = svc().get_settings(1)
    assert s.founder_id == 1
    assert s.reminders.reminder_time == DEFAULT_REMINDER_TIME and s.reminders.daily_reminders is True
    assert s.security.session_timeout_minutes == DEFAULT_SESSION_TIMEOUT_MINUTES
    assert s.security.login_notifications is True
    assert s.created_at == s.updated_at == T0


def test_get_is_idempotent():
    service = svc()
    first = service.get_settings(1)
    second = service.get_settings(1)
    assert first == second                                   # no second create, same timestamps


# --- partial updates --------------------------------------------------------


def test_update_reminders_partial_preserves_others():
    service = svc()
    service.get_settings(1)
    updated = service.update_reminders(1, reminder_time="07:30", daily_reminders=False)
    assert updated.reminders.reminder_time == "07:30" and updated.reminders.daily_reminders is False
    assert updated.reminders.task_reminders is True         # untouched
    assert updated.updated_at > updated.created_at


def test_update_security_partial():
    service = svc()
    updated = service.update_security(1, session_timeout_minutes=30)
    assert updated.security.session_timeout_minutes == 30
    assert updated.security.login_notifications is True      # untouched


def test_updates_persist_across_reads():
    service = svc()
    service.update_reminders(1, goal_reminders=False)
    assert service.get_settings(1).reminders.goal_reminders is False


# --- validation -------------------------------------------------------------


@pytest.mark.parametrize("bad", ["9:00", "25:00", "12:60", "noon", "", "0900"])
def test_invalid_reminder_time_rejected(bad):
    with pytest.raises(InvalidSettingError):
        svc().update_reminders(1, reminder_time=bad)


@pytest.mark.parametrize("bad", [0, 4, 1441, -10])
def test_invalid_session_timeout_rejected(bad):
    with pytest.raises(InvalidSettingError):
        svc().update_security(1, session_timeout_minutes=bad)


def test_valid_reminder_time_accepted():
    assert svc().update_reminders(1, reminder_time="23:59").reminders.reminder_time == "23:59"


# --- reset ------------------------------------------------------------------


def test_reset_restores_defaults():
    service = svc()
    service.update_reminders(1, reminder_time="06:00", daily_reminders=False)
    service.update_security(1, session_timeout_minutes=15)
    reset = service.reset_defaults(1)
    assert reset.reminders.reminder_time == DEFAULT_REMINDER_TIME and reset.reminders.daily_reminders is True
    assert reset.security.session_timeout_minutes == DEFAULT_SESSION_TIMEOUT_MINUTES


# --- isolation + determinism + concurrency ----------------------------------


def test_founder_isolation():
    service = svc()
    service.update_reminders(1, reminder_time="05:00")
    service.get_settings(2)
    assert service.get_settings(1).reminders.reminder_time == "05:00"
    assert service.get_settings(2).reminders.reminder_time == DEFAULT_REMINDER_TIME


def test_deterministic_execution():
    def run():
        service = svc()
        service.get_settings(1)
        service.update_reminders(1, reminder_time="08:15")
        return service.update_security(1, session_timeout_minutes=45)
    assert run() == run()


def test_concurrent_updates_across_founders():
    service = build_settings_service(InMemorySettingsRepository(), now=StepClock())

    def update(founder):
        return service.update_security(founder, session_timeout_minutes=30).founder_id

    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(update, range(1, 25)))
    assert sorted(ids) == list(range(1, 25))
    assert all(service.get_settings(f).security.session_timeout_minutes == 30 for f in range(1, 25))
