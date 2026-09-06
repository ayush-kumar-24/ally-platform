"""Domain tests for the Settings module. In-memory repo, deterministic.

The module used to own two sections, reminders and security. Both have shrunk:

* the four reminder settings (reminder_time, daily_reminders, task_reminders,
  goal_reminders) were removed on 2026-09-05 by team decision -- they validated,
  persisted and were read by nothing, and none was reachable in the UI;
* `session_timeout_minutes` went the same day, for the same reason plus a
  sharper one: a security setting that silently does nothing is a false
  assurance.

What remains is `login_notifications`, which now has a real consumer in
app/services/login_notifications.py. The tests below cover that, and pin the
removals so neither setting quietly comes back without a consumer.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from app.settings import (
    InMemorySettingsRepository,
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
    assert s.security.login_notifications is True
    assert s.created_at == s.updated_at == T0


def test_get_is_idempotent():
    service = svc()
    first = service.get_settings(1)
    second = service.get_settings(1)
    assert first == second                                   # no second create, same timestamps


# --- updates ----------------------------------------------------------------


def test_update_security_touches_updated_at():
    service = svc()
    service.get_settings(1)
    updated = service.update_security(1, login_notifications=False)
    assert updated.security.login_notifications is False
    assert updated.updated_at > updated.created_at


def test_update_with_nothing_sent_changes_nothing():
    """A PATCH carrying no fields must not flip anything -- partial means
    partial, including the empty case."""
    service = svc()
    before = service.get_settings(1)
    after = service.update_security(1)
    assert after.security == before.security


def test_updates_persist_across_reads():
    service = svc()
    service.update_security(1, login_notifications=False)
    assert service.get_settings(1).security.login_notifications is False


# --- the removals stay removed ----------------------------------------------


def test_reminder_settings_are_gone():
    """Removed 2026-09-05 by team decision: four settings that validated,
    persisted and were read by nothing. The section went with them."""
    service = svc()
    assert not hasattr(service, "update_reminders")
    assert not hasattr(service.get_settings(1), "reminders")


def test_session_timeout_is_gone():
    """Removed the same day. A founder choosing 5 minutes got the same 30-day
    session as everyone else, because nothing consulted the number."""
    with pytest.raises(TypeError):
        svc().update_security(1, session_timeout_minutes=30)


# --- reset ------------------------------------------------------------------


def test_reset_restores_defaults():
    service = svc()
    service.update_security(1, login_notifications=False)
    reset = service.reset_defaults(1)
    assert reset.security.login_notifications is True


def test_reset_on_a_founder_with_no_row_creates_one():
    assert svc().reset_defaults(99).founder_id == 99


# --- isolation + determinism + concurrency ----------------------------------


def test_founder_isolation():
    service = svc()
    service.update_security(1, login_notifications=False)
    service.get_settings(2)
    assert service.get_settings(1).security.login_notifications is False
    assert service.get_settings(2).security.login_notifications is True


def test_deterministic_execution():
    def run():
        service = svc()
        service.get_settings(1)
        return service.update_security(1, login_notifications=False)
    assert run() == run()


def test_concurrent_updates_across_founders():
    service = build_settings_service(InMemorySettingsRepository(), now=StepClock())

    def update(founder):
        return service.update_security(founder, login_notifications=False).founder_id

    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(update, range(1, 25)))
    assert sorted(ids) == list(range(1, 25))
    assert all(service.get_settings(f).security.login_notifications is False for f in range(1, 25))
