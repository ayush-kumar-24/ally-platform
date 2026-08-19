"""/auth/session must report the founder's real identity, and honest provisioning.

Two defects, both measured live against a founder that had existed for two days:

  * `provisioned: true` for a returning login. The flag was computed as
    `ensure_founder(...) is not None`, and that helper returns the row whether
    it created it or merely found it -- so it read true for every login, and
    for dev identities that provisioning explicitly never touches.

  * `founder.email` was the UPSTREAM identity's address. In dev mode that is a
    synthesised "<uuid>@ally.local", so the response advertised a fake address
    for a founder whose real one was in the row the call had just loaded.

The frontend happened to survive the second one by re-fetching /profile.
Anything trusting the session response did not.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.auth.base import AuthUser
from app.services import provisioning

BASE = "/api/v1/auth"

REAL_UUID = "3a729982-5325-44aa-90cd-476b51acd739"


class _Founder(SimpleNamespace):
    pass


@pytest.fixture
def no_rls(monkeypatch):
    """set_founder_rls_context talks to a live DB; irrelevant to these rules."""
    monkeypatch.setattr(provisioning, "set_founder_rls_context", lambda *a, **k: None)


def _identity(provider="dev", email=f"{REAL_UUID}@ally.local"):
    return AuthUser(id=REAL_UUID, email=email, provider=provider)


# --- ensure_founder_with_status -------------------------------------------

def test_existing_founder_is_found_not_provisioned(monkeypatch, no_rls):
    """The regression: a row that already existed must report created=False."""
    existing = _Founder(founder_id=11570, email="diag-fulltest+demo@verify.test")
    monkeypatch.setattr(
        provisioning.founder_repository, "get_by_user_id", lambda db, uid: existing
    )

    founder, created = provisioning.ensure_founder_with_status(_identity(), db=object())

    assert founder is existing
    assert created is False


def test_dev_identity_with_no_row_is_not_provisioned(monkeypatch, no_rls):
    """Dev never provisions -- founders.user_id is a FK to auth.users."""
    monkeypatch.setattr(
        provisioning.founder_repository, "get_by_user_id", lambda db, uid: None
    )

    founder, created = provisioning.ensure_founder_with_status(
        _identity(provider="dev"), db=object()
    )

    assert founder is None
    assert created is False


def test_non_uuid_subject_is_not_provisioned(no_rls):
    """A dev bearer that isn't a UUID has nothing to look up."""
    founder, created = provisioning.ensure_founder_with_status(
        AuthUser(id="not-a-uuid", provider="dev"), db=object()
    )

    assert founder is None
    assert created is False


def test_ensure_founder_still_returns_just_the_row(monkeypatch, no_rls):
    """The original one-value signature keeps working for its other callers."""
    existing = _Founder(founder_id=11570, email="diag-fulltest+demo@verify.test")
    monkeypatch.setattr(
        provisioning.founder_repository, "get_by_user_id", lambda db, uid: existing
    )

    assert provisioning.ensure_founder(_identity(), db=object()) is existing


# --- the response body -----------------------------------------------------

def test_session_reports_the_founder_row_email_not_the_identity(client, monkeypatch):
    """The response must carry the real address, not dev's <uuid>@ally.local."""
    from app.api.v1.auth import routes

    monkeypatch.setattr(
        routes,
        "ensure_founder_with_status",
        lambda identity, db, ip_address="0.0.0.0": (
            _Founder(founder_id=11570, email="diag-fulltest+demo@verify.test"),
            False,
        ),
    )

    body = client.post(f"{BASE}/session").json()

    assert body["founder"]["email"] == "diag-fulltest+demo@verify.test"
    assert not body["founder"]["email"].endswith("@ally.local")
    assert body["provisioned"] is False


def test_session_reports_provisioned_only_on_a_genuine_first_login(client, monkeypatch):
    from app.api.v1.auth import routes

    monkeypatch.setattr(
        routes,
        "ensure_founder_with_status",
        lambda identity, db, ip_address="0.0.0.0": (
            _Founder(founder_id=99999, email="brand-new@example.com"),
            True,
        ),
    )

    body = client.post(f"{BASE}/session").json()

    assert body["provisioned"] is True
    assert body["founder"]["email"] == "brand-new@example.com"


def test_session_falls_back_to_the_identity_email_with_no_founder(client, monkeypatch):
    """No row yet (dev, or provisioning off) -- the identity is all there is."""
    from app.api.v1.auth import routes

    monkeypatch.setattr(
        routes,
        "ensure_founder_with_status",
        lambda identity, db, ip_address="0.0.0.0": (None, False),
    )

    body = client.post(f"{BASE}/session").json()

    assert body["provisioned"] is False
    assert body["founder"]["id"]
