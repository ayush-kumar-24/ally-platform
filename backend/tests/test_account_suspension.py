"""Admin Panel Proposal, Gap #1: "Suspension does not lock anyone out."

Before this, `AdminPanelService.set_status` wrote `founders.status` and
nothing else in the app ever read it back -- a suspended founder's existing
access token, and any refresh token they already held, kept working exactly
as before until it naturally expired. The button and the audit row were real;
the lockout was not.

`is_account_active` is what closes that: `get_current_founder` (every
protected route) and `/auth/refresh` + `/auth/resume` all call it, so a
founder's very next request after being suspended is refused -- not their
next login, not whenever their token happens to expire.

Two layers here:
  - unit tests against a scriptable fake session -- the fail-open contract
    (missing row, missing column, a DB error) needs to be provable without a
    real database misbehaving on demand.
  - API tests through TestClient with `get_db` overridden -- proof the check
    is actually wired into the request path, not just correct in isolation.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.auth import factory
from app.core.auth.dependencies import is_account_active
from app.core.config import settings
from app.db.session import get_db
from app.main import app

BASE = "/api/v1/auth"
COOKIE = "ally_refresh_token"


# --- a scriptable stand-in for a SQLAlchemy Session -------------------------

class _Result:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value

    def scalar_one_or_none(self):
        # `/refresh` and `/resume` check SqlSessionStore.is_revoked on this
        # same fake session before reaching the suspension check -- these
        # tests are not exercising revocation, so it always reads "not
        # revoked" here regardless of the founder-status value below.
        return None


class FakeStatusSession:
    """Answers every query on the request with one canned founder status.

    Used for both the `founders.status` lookup (`is_account_active`) and,
    incidentally, the revoked-tokens lookup `SqlSessionStore` makes on the
    same request's `db` -- see `_Result.scalar_one_or_none` above.
    """

    def __init__(self, status_value: str | None = None, *, raise_on_execute: bool = False):
        self.status_value = status_value
        self.raise_on_execute = raise_on_execute
        self.rolled_back = False
        self.executed = False

    def execute(self, *args, **kwargs):
        self.executed = True
        if self.raise_on_execute:
            raise RuntimeError("simulated: database unreachable")
        return _Result(self.status_value)

    def rollback(self):
        self.rolled_back = True

    def commit(self):
        pass


# --- unit: is_account_active -------------------------------------------------

def test_active_status_is_active():
    assert is_account_active(FakeStatusSession("active"), "u1") is True


def test_inactive_status_is_still_active():
    """INACTIVE is a founder who hasn't been back in a while, not a lockout --
    only suspended/banned actually revoke access."""
    assert is_account_active(FakeStatusSession("inactive"), "u1") is True


def test_suspended_status_is_not_active():
    assert is_account_active(FakeStatusSession("suspended"), "u1") is False


def test_banned_status_is_not_active():
    assert is_account_active(FakeStatusSession("banned"), "u1") is False


def test_no_founder_row_fails_open():
    """No row yet (token minted, founder not provisioned) is not a suspension."""
    assert is_account_active(FakeStatusSession(None), "u1") is True


def test_db_error_fails_open_and_rolls_back():
    """A real suspension must never be masked by a DB hiccup -- but a DB hiccup
    must also never turn into "every authenticated request in the app is
    403ed". Fails open, and leaves the session clean for reuse."""
    db = FakeStatusSession(raise_on_execute=True)
    assert is_account_active(db, "u1") is True
    assert db.rolled_back is True


# --- API: the check is actually wired into the request path -----------------

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
    """Dev-mode login as a specific identity (any string becomes the founder
    id in dev), before any get_db override is installed -- /auth/session's
    provisioning check is unrelated to this fix and should not be exercised
    against a fake session."""
    r = client.post(f"{BASE}/session", headers={"Authorization": f"Bearer {founder_token}"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"], r.cookies.get(COOKIE)


def test_active_founder_reaches_me(dev_client):
    access, _ = _issue(dev_client, "founder-active")
    app.dependency_overrides[get_db] = lambda: FakeStatusSession("active")
    r = dev_client.get(f"{BASE}/me", headers={"Authorization": f"Bearer {access}"})
    assert r.status_code == 200


def test_suspended_founder_is_rejected_on_the_very_next_request(dev_client):
    """The bug, made concrete: the SAME access token that worked a moment ago
    -- unexpired, unrevoked, cryptographically fine -- now fails, because the
    account status is checked live and not just baked into the token."""
    access, _ = _issue(dev_client, "founder-suspended")
    app.dependency_overrides[get_db] = lambda: FakeStatusSession("suspended")
    r = dev_client.get(f"{BASE}/me", headers={"Authorization": f"Bearer {access}"})
    assert r.status_code == 403


def test_banned_founder_is_rejected(dev_client):
    access, _ = _issue(dev_client, "founder-banned")
    app.dependency_overrides[get_db] = lambda: FakeStatusSession("banned")
    r = dev_client.get(f"{BASE}/me", headers={"Authorization": f"Bearer {access}"})
    assert r.status_code == 403


def test_a_missing_status_column_does_not_lock_out_the_whole_app(dev_client):
    """Deployed before the column exists on a given database (Supabase vs. RDS
    drift is a live concern for this project) -- must fail open, not 500 or
    403 every request."""
    access, _ = _issue(dev_client, "founder-precolumn")
    app.dependency_overrides[get_db] = lambda: FakeStatusSession(raise_on_execute=True)
    r = dev_client.get(f"{BASE}/me", headers={"Authorization": f"Bearer {access}"})
    assert r.status_code == 200


def test_suspended_founder_cannot_refresh_to_a_new_access_token(dev_client):
    """Closes the loophole a suspend-then-refresh could otherwise leave: a
    suspended founder should not be able to mint a fresh, unflagged token at
    all -- not even one that would immediately 403 on first use."""
    _, refresh = _issue(dev_client, "founder-suspended-2")
    app.dependency_overrides[get_db] = lambda: FakeStatusSession("suspended")
    r = dev_client.post(f"{BASE}/refresh", cookies={COOKIE: refresh})
    assert r.status_code == 403


def test_suspended_founder_cannot_resume_a_session(dev_client):
    _, refresh = _issue(dev_client, "founder-suspended-3")
    app.dependency_overrides[get_db] = lambda: FakeStatusSession("banned")
    r = dev_client.post(f"{BASE}/resume", cookies={COOKIE: refresh})
    assert r.status_code == 403
