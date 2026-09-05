"""Admin Panel Proposal, Gap #2: "No live-user view."

`founders.last_active_at` has existed since the same migration that added
`status` (Phase 1's fix), but nothing in the app ever wrote it -- the
dashboard's "Active today" card ran a real query against a real column and
always answered 0, because the column was permanently empty. `record_last_active`
is that missing write: called from `get_current_founder` on every protected
route, and from `/auth/refresh` + `/auth/resume`, on every request a founder
is confirmed active for.

Mirrors test_account_suspension.py's two layers:
  - unit tests against a scriptable fake session -- the throttle SQL and the
    fail-open contract need to be provable without a real database.
  - API tests through TestClient with `get_db` overridden -- proof the write
    is actually reached from the request path.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.auth import factory
from app.core.auth.dependencies import _LAST_ACTIVE_THROTTLE, record_last_active
from app.core.config import settings
from app.db.session import get_db
from app.main import app

BASE = "/api/v1/auth"
COOKIE = "ally_refresh_token"
NOW = datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)


# --- a scriptable stand-in for a SQLAlchemy Session -------------------------

class RecordingSession:
    def __init__(self, *, raise_on_execute: bool = False):
        self.raise_on_execute = raise_on_execute
        self.executed: list[tuple[str, dict]] = []
        self.committed = False
        self.rolled_back = False

    def execute(self, clause, params=None):
        if self.raise_on_execute:
            raise RuntimeError("simulated: database unreachable")
        self.executed.append((str(clause), params or {}))
        return None

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    # SqlSessionStore's revoked-token check runs on the same session in the
    # /refresh and /resume tests below.
    def scalar(self):
        return None


class RecordingResultSession(RecordingSession):
    """As above, but `execute` returns something `.scalar_one_or_none()` can
    be called on, for the /refresh and /resume paths that also check
    SqlSessionStore.is_revoked on this session before reaching this write."""

    def execute(self, clause, params=None):
        super().execute(clause, params)

        class _Result:
            def scalar_one_or_none(self_):
                return None  # "not revoked" and "not suspended" alike

            def scalar(self_):
                return None

        return _Result()

    def add(self, *args, **kwargs):
        pass  # SqlSessionStore.revoke() adds a RevokedTokenRow after this check passes


# --- unit: record_last_active -----------------------------------------------

def test_writes_last_active_at_for_the_given_founder():
    db = RecordingSession()
    record_last_active(db, "founder-1", now=NOW)

    assert db.committed is True
    sql, params = db.executed[0]
    assert "update founders" in sql.lower()
    assert "last_active_at" in sql.lower()
    assert params["uid"] == "founder-1"
    assert params["at"] == NOW


def test_the_throttle_window_matches_the_configured_constant():
    db = RecordingSession()
    record_last_active(db, "founder-1", now=NOW)

    _, params = db.executed[0]
    assert params["threshold"] == NOW - _LAST_ACTIVE_THROTTLE


def test_a_db_error_is_swallowed_and_rolls_back():
    """This write only measures activity -- it must never be the reason a real
    request fails, so a DB hiccup here is silent, not raised."""
    db = RecordingSession(raise_on_execute=True)
    record_last_active(db, "founder-1", now=NOW)  # must not raise
    assert db.rolled_back is True


def test_defaults_to_the_current_time_when_none_is_given():
    db = RecordingSession()
    before = datetime.now(timezone.utc)
    record_last_active(db, "founder-1")
    after = datetime.now(timezone.utc)

    _, params = db.executed[0]
    assert before <= params["at"] <= after


# --- API: the write is actually reached from the request path ---------------

@pytest.fixture
def dev_client():
    original = settings.AUTH_PROVIDER
    settings.AUTH_PROVIDER = "dev"
    factory.get_auth_provider.cache_clear()
    yield TestClient(app)
    settings.AUTH_PROVIDER = original
    factory.get_auth_provider.cache_clear()
    app.dependency_overrides.pop(get_db, None)


def _issue(client: TestClient, founder_token: str) -> tuple[str, str]:
    r = client.post(f"{BASE}/session", headers={"Authorization": f"Bearer {founder_token}"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"], r.cookies.get(COOKIE)


def test_me_records_activity_for_the_calling_founder(dev_client):
    access, _ = _issue(dev_client, "founder-active-tracking")
    db = RecordingSession()
    app.dependency_overrides[get_db] = lambda: db

    r = dev_client.get(f"{BASE}/me", headers={"Authorization": f"Bearer {access}"})
    assert r.status_code == 200
    assert db.committed is True
    _, params = db.executed[-1]
    assert params["uid"] == "founder-active-tracking"


def test_refresh_records_activity_too(dev_client):
    _, refresh = _issue(dev_client, "founder-active-refresh")
    db = RecordingResultSession()
    app.dependency_overrides[get_db] = lambda: db

    r = dev_client.post(f"{BASE}/refresh", cookies={COOKIE: refresh})
    assert r.status_code == 200
    updates = [p for _, p in db.executed if "uid" in p]
    assert any(p["uid"] == "founder-active-refresh" for p in updates)


def test_a_write_failure_never_breaks_the_actual_request(dev_client):
    """The founder still gets their /me response even when the activity write
    itself is broken."""
    access, _ = _issue(dev_client, "founder-write-fails")

    class _SuspensionOkThenRaises:
        def __init__(self):
            self.calls = 0

        def execute(self, clause, params=None):
            self.calls += 1
            if self.calls == 1:
                class _R:
                    def scalar(self_):
                        return None  # is_account_active: no row -> active
                return _R()
            raise RuntimeError("simulated: last-active write fails")

        def rollback(self):
            pass

    app.dependency_overrides[get_db] = lambda: _SuspensionOkThenRaises()
    r = dev_client.get(f"{BASE}/me", headers={"Authorization": f"Bearer {access}"})
    assert r.status_code == 200
