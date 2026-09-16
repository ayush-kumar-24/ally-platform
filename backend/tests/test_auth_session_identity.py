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
    """A stand-in for the Founder row, with `user_id` defaulted.

    The real row always has one, and since the Cognito migration (53e3b46)
    /auth/session reads it: Ally's own JWT must carry the canonical
    `founder.user_id` rather than the upstream provider subject, because a
    migrated user's Cognito sub is new while their Supabase UUID is what all
    their existing data hangs off.

    A bare SimpleNamespace has only the attributes it is handed, so every test
    here raised `AttributeError: '_Founder' object has no attribute 'user_id'`
    the moment that line landed. It went unnoticed because these tests could
    not run at all -- they errored during fixture setup, before reaching the
    code under test, for reasons that had nothing to do with this.
    """

    def __init__(self, **kwargs):
        kwargs.setdefault("user_id", REAL_UUID)
        super().__init__(**kwargs)


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
        "ensure_founder_or_waitlist",
        lambda identity, db, ip_address="0.0.0.0": (
            _Founder(founder_id=11570, email="diag-fulltest+demo@verify.test"),
            False,
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
        "ensure_founder_or_waitlist",
        lambda identity, db, ip_address="0.0.0.0": (
            _Founder(founder_id=99999, email="brand-new@example.com"),
            True,
            False,
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
        "ensure_founder_or_waitlist",
        lambda identity, db, ip_address="0.0.0.0": (None, False, False),
    )

    body = client.post(f"{BASE}/session").json()

    assert body["provisioned"] is False
    assert body["founder"]["id"]


def test_session_reports_waitlisted_for_a_direct_signup_past_capacity(client, monkeypatch):
    """The one NEW outcome: no founder, no ordinary 'not provisioned' either --
    the frontend needs to tell this apart to show a waitlist message rather
    than a broken onboarding screen."""
    from app.api.v1.auth import routes

    monkeypatch.setattr(
        routes,
        "ensure_founder_or_waitlist",
        lambda identity, db, ip_address="0.0.0.0": (None, False, True),
    )

    body = client.post(f"{BASE}/session").json()

    assert body["provisioned"] is False
    assert body["waitlisted"] is True


# --- ensure_founder_or_waitlist: the direct-signup capacity gate -----------
#
# A SQL-aware stub rather than a real database: what is under test here is
# the BRANCHING -- which query runs, in what order, and what the function
# does with each answer -- not Postgres's own row-locking, which no amount of
# mocking can honestly exercise anyway. The FOR UPDATE claim's actual
# concurrency guarantee is a property of Postgres, not of this function; this
# suite pins that the function asks for it and respects the answer.


class _CapacityStubSession:
    """Answers exactly the queries ensure_founder_or_waitlist is allowed to
    issue, by sniffing the SQL text. Anything else raises, so a query this
    function starts issuing without a matching test update is a loud failure,
    not a silently-wrong stub answer."""

    def __init__(self, *, waitlist_approved: bool, capacity_remaining: int):
        self.waitlist_approved = waitlist_approved
        self.capacity_remaining = capacity_remaining
        self.registered: list[dict] = []
        self.rolled_back = False
        self.committed = False

    def execute(self, stmt, params=None):
        sql = str(stmt)
        if "app.current_founder_uuid" in sql:
            return SimpleNamespace(scalar=lambda: None, scalar_one=lambda: None)
        if "waitlist_registrations" in sql and "auth_user_id" in sql:
            return SimpleNamespace(scalar=lambda: self.waitlist_approved)
        if "FOR UPDATE" in sql:
            return SimpleNamespace(scalar_one=lambda: self.capacity_remaining)
        if "SET remaining = remaining - 1" in sql:
            self.capacity_remaining -= 1
            return SimpleNamespace(scalar=lambda: None)
        raise AssertionError(f"unexpected query in capacity gate test: {sql!r}")

    def rollback(self):
        self.rolled_back = True

    def commit(self):
        self.committed = True


def _new_identity():
    return AuthUser(id=REAL_UUID, provider="google", email="new@example.com")


@pytest.fixture
def no_existing_founder(monkeypatch, no_rls):
    """No founders row for this identity -- the branch under test."""
    monkeypatch.setattr(
        provisioning.founder_repository, "get_by_user_id", lambda db, uid: None
    )


def test_an_approved_waitlist_founder_is_never_capacity_checked(
    monkeypatch, no_existing_founder
):
    """The team already said yes to this person on a different ledger. Direct
    capacity reading zero must not undo that."""
    db = _CapacityStubSession(waitlist_approved=True, capacity_remaining=0)
    sentinel = SimpleNamespace(founder_id=1)
    monkeypatch.setattr(
        provisioning,
        "ensure_founder_with_status",
        lambda identity, db, ip_address="0.0.0.0": (sentinel, True),
    )

    founder, created, waitlisted = provisioning.ensure_founder_or_waitlist(
        _new_identity(), db
    )

    assert (founder, created, waitlisted) == (sentinel, True, False)


def test_a_direct_signup_inside_capacity_is_provisioned_and_a_slot_is_spent(
    monkeypatch, no_existing_founder
):
    db = _CapacityStubSession(waitlist_approved=False, capacity_remaining=3)
    sentinel = SimpleNamespace(founder_id=2)
    monkeypatch.setattr(
        provisioning,
        "ensure_founder_with_status",
        lambda identity, db, ip_address="0.0.0.0": (sentinel, True),
    )

    founder, created, waitlisted = provisioning.ensure_founder_or_waitlist(
        _new_identity(), db
    )

    assert (founder, created, waitlisted) == (sentinel, True, False)
    assert db.capacity_remaining == 2  # the slot was actually spent


def test_a_direct_signup_at_zero_capacity_is_queued_not_provisioned(
    monkeypatch, no_existing_founder
):
    """The outcome the whole feature exists for: no slot, no founder row --
    and the address lands in the same pending queue register() always fills."""
    db = _CapacityStubSession(waitlist_approved=False, capacity_remaining=0)
    registered = []
    monkeypatch.setattr(
        provisioning, "register",
        lambda db, **kw: registered.append(kw),
    )
    monkeypatch.setattr(
        provisioning, "send_direct_signup_overflow_email", lambda *a, **k: True
    )
    # Must NOT be reached: zero capacity means no attempt to provision at all.
    monkeypatch.setattr(
        provisioning,
        "ensure_founder_with_status",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not provision")),
    )

    founder, created, waitlisted = provisioning.ensure_founder_or_waitlist(
        _new_identity(), db
    )

    assert (founder, created, waitlisted) == (None, False, True)
    assert db.rolled_back is True  # the FOR UPDATE lock is released, nothing kept
    assert registered == [{
        "email": "new@example.com", "full_name": "new",
        "source": "direct_signup_overflow", "ip_address": "0.0.0.0",
    }]


def test_the_overflow_email_failing_does_not_fail_the_sign_in(
    monkeypatch, no_existing_founder
):
    """Same never-block contract as every other best-effort mail in this
    codebase: the queue entry is already committed by register(); the founder
    still gets a clean (None, False, True), not a 500."""
    db = _CapacityStubSession(waitlist_approved=False, capacity_remaining=0)
    monkeypatch.setattr(provisioning, "register", lambda db, **kw: None)

    def boom(*_a, **_k):
        raise RuntimeError("smtp down")

    monkeypatch.setattr(provisioning, "send_direct_signup_overflow_email", boom)

    founder, created, waitlisted = provisioning.ensure_founder_or_waitlist(
        _new_identity(), db
    )

    assert (founder, created, waitlisted) == (None, False, True)


def test_dev_identity_never_reaches_the_capacity_gate(no_rls):
    """Dev has no auth.users row; the gate must not run a real query against
    one. Covered implicitly by no_rls's founder_repository stub being absent
    here -- a real DB call would raise on db=object()."""
    founder, created, waitlisted = provisioning.ensure_founder_or_waitlist(
        AuthUser(id="not-a-uuid", provider="dev"), db=object()
    )
    assert (founder, created, waitlisted) == (None, False, False)
