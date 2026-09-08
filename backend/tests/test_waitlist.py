"""Waitlist: the cap, the approval ordering, and the public form's silence.

Hermetic like the rest of the suite -- no database. The service takes a
Session, so the tests hand it a stub that records what was asked of it. That is
enough to pin the behaviour that actually matters here, which is ORDER and
FAILURE HANDLING rather than SQL: the identity must exist before the row is
marked, and a failed email must not undo a grant.
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from app.admin.rbac import Capability, PanelRole, has_capability
from app.core.config import settings
from app.main import app
from app.models.waitlist import APPROVED, PENDING, REJECTED
from app.services import supabase_admin, waitlist
from app.services.waitlist import (
    RegistrationNotPendingError,
    WaitlistCapReachedError,
    normalise_email,
)

UID = UUID("11111111-2222-3333-4444-555555555555")


class Row:
    """Stands in for a WaitlistRegistration. Plain attributes, because the
    service only ever reads and assigns them."""

    def __init__(self, status=PENDING, email="f@x.com", name="Priya Sharma"):
        self.registration_id = 1
        self.email = email
        self.full_name = name
        self.status = status
        self.decided_at = None
        self.decided_by_admin_id = None
        self.decided_by_email = None
        self.decision_reason = None
        self.auth_user_id = None
        self.access_granted_at = None
        self.approval_email_sent_at = None


class StubSession:
    """Enough Session for the service: a scalar for the cap count, a row for
    the SELECT ... FOR UPDATE, and a record of commits/rollbacks.

    `scalar_one` answers the approved count and `scalar` the opened-slots sum,
    which is the only reason the service reads those two through different
    methods -- a stub that returned one number for both could not tell the cap
    apart from the ledger.
    """

    def __init__(self, row=None, approved_count=0, slots_opened=0):
        self._row = row
        self._approved = approved_count
        self._slots_opened = slots_opened
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    def execute(self, *_a, **_k):
        return self

    def scalar_one(self):
        return self._approved

    def scalar(self):
        return self._slots_opened

    def scalar_one_or_none(self):
        return self._row

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def refresh(self, _row):
        pass


# --- the capability -------------------------------------------------------


def test_manage_waitlist_is_admin_and_super_admin_not_support():
    assert has_capability(PanelRole.ADMIN, Capability.MANAGE_WAITLIST)
    assert has_capability(PanelRole.SUPER_ADMIN, Capability.MANAGE_WAITLIST)
    # Support can see the queue (VIEW_USERS) but must not be able to let
    # anyone in.
    assert not has_capability(PanelRole.SUPPORT, Capability.MANAGE_WAITLIST)
    assert has_capability(PanelRole.SUPPORT, Capability.VIEW_USERS)


def test_normalise_email_is_the_one_definition_of_same_person():
    assert normalise_email("  Priya@Example.COM ") == "priya@example.com"


# --- the cap --------------------------------------------------------------


def test_cap_status_reports_remaining(monkeypatch):
    monkeypatch.setattr(settings, "WAITLIST_APPROVAL_CAP", 300)
    assert waitlist.cap_status(StubSession(approved_count=298)) == {
        "approved": 298, "cap": 300, "base_cap": 300, "slots_opened": 0,
        "remaining": 2, "is_full": False,
    }


def test_cap_status_never_reports_negative_remaining(monkeypatch):
    """Over the cap (a super admin approved past it) must read as 0 left, not -5."""
    monkeypatch.setattr(settings, "WAITLIST_APPROVAL_CAP", 300)
    s = waitlist.cap_status(StubSession(approved_count=305))
    assert s["remaining"] == 0 and s["is_full"] is True


def test_admin_is_refused_at_the_cap_and_no_identity_is_created(monkeypatch):
    monkeypatch.setattr(settings, "WAITLIST_APPROVAL_CAP", 300)
    called = []
    monkeypatch.setattr(waitlist, "create_auth_user", lambda *a, **k: called.append(1))
    db = StubSession(row=Row(), approved_count=300)

    with pytest.raises(WaitlistCapReachedError):
        waitlist.approve(db, 1, admin_id=1, admin_email="a@x.com", admin_role=PanelRole.ADMIN)

    # The cap is checked BEFORE the irreversible step, so nothing was created.
    assert called == []
    assert db.commits == 0 and db.rollbacks == 1


def test_super_admin_may_approve_past_the_cap(monkeypatch):
    monkeypatch.setattr(settings, "WAITLIST_APPROVAL_CAP", 300)
    monkeypatch.setattr(waitlist, "create_auth_user", lambda *a, **k: UID)
    monkeypatch.setattr(waitlist, "send_approval_email", lambda *a, **k: True)
    row = Row()

    out = waitlist.approve(
        StubSession(row=row, approved_count=300),
        1, admin_id=1, admin_email="s@x.com", admin_role=PanelRole.SUPER_ADMIN,
    )
    assert out.status == APPROVED and out.auth_user_id == UID


# --- approval ordering ----------------------------------------------------


def test_a_failed_identity_leaves_the_row_pending(monkeypatch):
    """The row must not be marked approved when the founder cannot log in."""
    monkeypatch.setattr(settings, "WAITLIST_APPROVAL_CAP", 300)

    def boom(*_a, **_k):
        raise supabase_admin.IdentityProviderError("upstream said no")

    monkeypatch.setattr(waitlist, "create_auth_user", boom)
    row = Row()
    db = StubSession(row=row, approved_count=0)

    with pytest.raises(supabase_admin.IdentityProviderError):
        waitlist.approve(db, 1, admin_id=1, admin_email="a@x.com", admin_role=PanelRole.ADMIN)

    assert row.status == PENDING and row.auth_user_id is None
    assert db.commits == 0


def test_a_failed_email_does_not_undo_the_grant(monkeypatch):
    """The identity exists and the row is committed; only the sent-marker is absent."""
    monkeypatch.setattr(settings, "WAITLIST_APPROVAL_CAP", 300)
    monkeypatch.setattr(waitlist, "create_auth_user", lambda *a, **k: UID)

    def boom(*_a, **_k):
        raise RuntimeError("smtp down")

    monkeypatch.setattr(waitlist, "send_approval_email", boom)
    row = Row()

    out = waitlist.approve(
        StubSession(row=row, approved_count=0),
        1, admin_id=1, admin_email="a@x.com", admin_role=PanelRole.ADMIN,
    )
    assert out.status == APPROVED and out.auth_user_id == UID
    # Not sent -- so the panel can show this founder still needs chasing.
    assert out.approval_email_sent_at is None


def test_email_send_marker_is_only_set_when_it_actually_sent(monkeypatch):
    monkeypatch.setattr(settings, "WAITLIST_APPROVAL_CAP", 300)
    monkeypatch.setattr(waitlist, "create_auth_user", lambda *a, **k: UID)
    # send_email returns False in stub mode (no EMAIL_HOST) -- that is not a send.
    monkeypatch.setattr(waitlist, "send_approval_email", lambda *a, **k: False)

    out = waitlist.approve(
        StubSession(row=Row(), approved_count=0),
        1, admin_id=1, admin_email="a@x.com", admin_role=PanelRole.ADMIN,
    )
    assert out.approval_email_sent_at is None


def test_an_already_decided_registration_cannot_be_approved_twice(monkeypatch):
    monkeypatch.setattr(settings, "WAITLIST_APPROVAL_CAP", 300)
    for decided in (APPROVED, REJECTED):
        with pytest.raises(RegistrationNotPendingError):
            waitlist.approve(
                StubSession(row=Row(status=decided)),
                1, admin_id=1, admin_email="a@x.com", admin_role=PanelRole.ADMIN,
            )


def test_reject_records_who_and_why_and_sends_nothing(monkeypatch):
    sent = []
    monkeypatch.setattr(waitlist, "send_approval_email", lambda *a, **k: sent.append(1))
    row = Row()

    out = waitlist.reject(
        StubSession(row=row), 1, reason="  not a founder yet  ",
        admin_id=7, admin_email="a@x.com",
    )
    assert out.status == REJECTED
    assert out.decision_reason == "not a founder yet"
    assert out.decided_by_admin_id == 7
    assert sent == []


# --- the identity provider ------------------------------------------------


def test_approval_refuses_outright_when_no_service_role_key(monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "")
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://p.supabase.co")
    assert supabase_admin.is_configured() is False
    with pytest.raises(supabase_admin.IdentityProviderNotConfigured):
        supabase_admin.create_auth_user("f@x.com")


def test_create_auth_user_returns_the_new_id(monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "svc")
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://p.supabase.co")
    new_id = uuid4()

    class Resp:
        status_code = 201

        @staticmethod
        def json():
            return {"id": str(new_id)}

    monkeypatch.setattr(supabase_admin.httpx, "post", lambda *a, **k: Resp())
    assert supabase_admin.create_auth_user("f@x.com", full_name="Priya") == new_id


def test_an_existing_identity_is_recovered_rather_than_failing(monkeypatch):
    """A 422 means someone already has this address -- created by hand, or by a
    previous approval that lost the response. Recovering the id is what stops
    that registration being permanently unapprovable."""
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "svc")
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://p.supabase.co")
    existing = uuid4()

    class Post:
        status_code = 422

        @staticmethod
        def json():
            return {"msg": "already registered"}

    class Get:
        status_code = 200

        @staticmethod
        def raise_for_status():
            pass

        @staticmethod
        def json():
            return {"users": [{"id": str(existing), "email": "F@X.com"}]}

    monkeypatch.setattr(supabase_admin.httpx, "post", lambda *a, **k: Post())
    monkeypatch.setattr(supabase_admin.httpx, "get", lambda *a, **k: Get())
    assert supabase_admin.create_auth_user("f@x.com") == existing


def test_an_upstream_refusal_raises_rather_than_returning_none(monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "svc")
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://p.supabase.co")

    class Resp:
        status_code = 500

        @staticmethod
        def json():
            return {}

    monkeypatch.setattr(supabase_admin.httpx, "post", lambda *a, **k: Resp())
    with pytest.raises(supabase_admin.IdentityProviderError):
        supabase_admin.create_auth_user("f@x.com")


# --- the public form ------------------------------------------------------


@pytest.fixture
def public_client(monkeypatch):
    """TestClient with the DB dependency stubbed out -- the endpoint's own
    behaviour is what is under test, not the insert."""
    from fastapi.testclient import TestClient

    from app.api.v1.waitlist import public as public_mod
    from app.db.session import get_db

    recorded: list[dict] = []
    monkeypatch.setattr(
        public_mod, "register", lambda db, **kw: recorded.append(kw)
    )
    app.dependency_overrides[get_db] = lambda: None
    # The rate limiter is in-process and shared across tests; bypass it so a
    # neighbouring test's traffic cannot fail this one.
    app.dependency_overrides[public_mod.waitlist_rate_limit] = lambda: None
    yield TestClient(app), recorded
    app.dependency_overrides.clear()


def test_a_registration_is_accepted(public_client):
    client, recorded = public_client
    r = client.post("/api/v1/waitlist", json={
        "email": "Priya@Example.com", "full_name": "Priya Sharma",
        "company": "LoopCart", "note": "building D2C logistics",
    })
    assert r.status_code == 202
    assert len(recorded) == 1
    assert recorded[0]["email"] == "Priya@Example.com"
    assert recorded[0]["full_name"] == "Priya Sharma"


def test_the_honeypot_is_accepted_and_discarded(public_client):
    """A bot must get the same 202 a human does -- an error is a signal it can
    iterate against -- and must not reach the table."""
    client, recorded = public_client
    r = client.post("/api/v1/waitlist", json={
        "email": "bot@x.com", "full_name": "Bot", "website": "http://spam.example",
    })
    assert r.status_code == 202
    assert recorded == []


def test_the_response_body_is_identical_for_new_and_duplicate(public_client):
    """The endpoint must not be an existence oracle over the founder list."""
    client, _ = public_client
    body = {"email": "same@x.com", "full_name": "Same Person"}
    first = client.post("/api/v1/waitlist", json=body)
    second = client.post("/api/v1/waitlist", json=body)
    assert first.status_code == second.status_code == 202
    assert first.json() == second.json()


def test_an_unknown_field_is_rejected_rather_than_silently_dropped(public_client):
    client, _ = public_client
    r = client.post("/api/v1/waitlist", json={
        "email": "f@x.com", "full_name": "F", "revenue": "10L",
    })
    assert r.status_code == 422


# --- the approval email ---------------------------------------------------


def test_the_email_links_to_the_platform_not_the_marketing_site(monkeypatch):
    """PUBLIC_APP_URL points at the marketing site in production, which has no
    /guided/* route -- preferring it would send every approved founder to a 404."""
    from app.services import waitlist_notifications as wn

    monkeypatch.setattr(settings, "SHARE_LINK_BASE_URL", "https://app.goxlally.ai")
    monkeypatch.setattr(settings, "PUBLIC_APP_URL", "https://goxlally.ai")
    assert wn._sign_in_url() == "https://app.goxlally.ai/guided/login"


def test_the_email_drops_the_link_rather_than_emitting_a_broken_one(monkeypatch):
    from app.services import waitlist_notifications as wn

    monkeypatch.setattr(settings, "SHARE_LINK_BASE_URL", "")
    monkeypatch.setattr(settings, "PUBLIC_APP_URL", "")
    assert wn._sign_in_url() == ""

    captured = {}
    monkeypatch.setattr(
        wn, "send_email",
        lambda to, subject, text, html=None: captured.update(text=text, html=html) or True,
    )
    assert wn.send_approval_email("f@x.com", "Priya Sharma") is True
    assert "href" not in captured["html"]
    assert "http" not in captured["text"]


def test_the_email_greets_by_first_name_and_survives_a_blank_one(monkeypatch):
    from app.services import waitlist_notifications as wn

    captured = {}
    monkeypatch.setattr(
        wn, "send_email",
        lambda to, subject, text, html=None: captured.update(text=text) or True,
    )
    wn.send_approval_email("f@x.com", "Priya Sharma")
    assert "Hi Priya," in captured["text"]

    wn.send_approval_email("f@x.com", "   ")
    assert "Hi there," in captured["text"]


# --- opening slots --------------------------------------------------------


def test_opening_slots_is_super_admin_only():
    """Approving one person is queue work; deciding how many people the phase
    holds is not. Admin can clear the queue and still cannot grow it."""
    assert has_capability(PanelRole.SUPER_ADMIN, Capability.OPEN_WAITLIST_SLOTS)
    assert not has_capability(PanelRole.ADMIN, Capability.OPEN_WAITLIST_SLOTS)
    assert not has_capability(PanelRole.SUPPORT, Capability.OPEN_WAITLIST_SLOTS)
    # ...while the ordinary approval stays where it was.
    assert has_capability(PanelRole.ADMIN, Capability.MANAGE_WAITLIST)


def test_the_cap_is_the_env_value_plus_every_slot_opened(monkeypatch):
    """The environment keeps meaning "the size we launched with". Slots opened
    from the panel add to it, so a deploy cannot silently undo them."""
    monkeypatch.setattr(settings, "WAITLIST_APPROVAL_CAP", 300)
    status = waitlist.cap_status(StubSession(approved_count=300, slots_opened=25))
    assert status["cap"] == 325
    assert status["base_cap"] == 300 and status["slots_opened"] == 25
    # Full a moment ago, not full now -- which is the whole point of the feature.
    assert status["is_full"] is False and status["remaining"] == 25


def _queue(*names):
    rows = []
    for i, name in enumerate(names, start=1):
        row = Row(name=name, email=f"{name.lower()}@x.com")
        row.registration_id = i
        rows.append(row)
    return rows


def _open(db, monkeypatch, queue, approve_impl, slots=3):
    monkeypatch.setattr(waitlist, "next_in_queue", lambda _db, n: queue[:n])
    monkeypatch.setattr(waitlist, "approve", approve_impl)
    return waitlist.open_slots(
        db, slots=slots, admin_id=7, admin_email="s@x.com",
        admin_role=PanelRole.SUPER_ADMIN,
    )


def test_slots_approve_the_front_of_the_queue_in_order(monkeypatch):
    """The order people asked in is the order they get in. An admin who opens
    three slots gets exactly the three rows at the top of their screen."""
    monkeypatch.setattr(settings, "WAITLIST_APPROVAL_CAP", 300)
    queue = _queue("Asha", "Bala", "Chetan", "Divya")
    seen = []

    def fake_approve(_db, registration_id, **_k):
        row = next(r for r in queue if r.registration_id == registration_id)
        seen.append(row.full_name)
        row.status = APPROVED
        return row

    out = _open(StubSession(), monkeypatch, queue, fake_approve, slots=3)

    assert seen == ["Asha", "Bala", "Chetan"]
    assert [r.full_name for r in out["approved"]] == ["Asha", "Bala", "Chetan"]
    # The fourth stays where they were: at the front of the next opening.
    assert queue[3].status == PENDING


def test_the_opening_is_recorded_before_anyone_is_approved(monkeypatch):
    """The ledger row must be committed first, or `approve` would check a cap
    that has not moved yet and refuse every approval in its own batch."""
    monkeypatch.setattr(settings, "WAITLIST_APPROVAL_CAP", 300)
    db = StubSession()
    queue = _queue("Asha")
    commits_when_approving = []

    def fake_approve(_db, registration_id, **_k):
        commits_when_approving.append(db.commits)
        row = queue[0]
        row.status = APPROVED
        return row

    _open(db, monkeypatch, queue, fake_approve, slots=1)

    opening = db.added[0]
    assert opening.slots_opened == 1
    assert opening.opened_by_email == "s@x.com" and opening.opened_by_admin_id == 7
    # At least one commit had already happened when the first approval ran.
    assert commits_when_approving and commits_when_approving[0] >= 1


def test_one_failure_does_not_deny_the_rest_their_place(monkeypatch):
    """Each approval is its own transaction, so a single identity call failing
    is reported against that person and nobody else's place is lost."""
    monkeypatch.setattr(settings, "WAITLIST_APPROVAL_CAP", 300)
    queue = _queue("Asha", "Bala", "Chetan")

    def fake_approve(_db, registration_id, **_k):
        row = next(r for r in queue if r.registration_id == registration_id)
        if row.full_name == "Bala":
            raise supabase_admin.IdentityProviderError("upstream said no")
        row.status = APPROVED
        return row

    out = _open(StubSession(), monkeypatch, queue, fake_approve, slots=3)

    assert [r.full_name for r in out["approved"]] == ["Asha", "Chetan"]
    assert len(out["failures"]) == 1
    assert out["failures"][0]["full_name"] == "Bala"
    assert out["failures"][0]["email"] == "bala@x.com"
    # Still pending, so opening slots again retries them from the front.
    assert queue[1].status == PENDING


def test_an_opening_bigger_than_the_queue_keeps_the_unused_places(monkeypatch):
    """Ten slots against a queue of two is not an error: eight places stay open
    for whoever registers next, and the ledger says only two were used."""
    monkeypatch.setattr(settings, "WAITLIST_APPROVAL_CAP", 300)
    db = StubSession()
    queue = _queue("Asha", "Bala")

    def fake_approve(_db, registration_id, **_k):
        row = next(r for r in queue if r.registration_id == registration_id)
        row.status = APPROVED
        return row

    out = _open(db, monkeypatch, queue, fake_approve, slots=10)

    assert len(out["approved"]) == 2 and out["slots"] == 10
    opening = db.added[0]
    assert opening.slots_opened == 10 and opening.approved_count == 2


def test_opening_zero_or_fewer_slots_is_refused(monkeypatch):
    monkeypatch.setattr(settings, "WAITLIST_APPROVAL_CAP", 300)
    for bad in (0, -5):
        with pytest.raises(ValueError):
            waitlist.open_slots(
                StubSession(), slots=bad, admin_id=1, admin_email="s@x.com",
                admin_role=PanelRole.SUPER_ADMIN,
            )
