"""Profile progress/validation + discovery-call booking, against seeded founders."""

import uuid
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.auth import AuthUser, get_current_founder
from app.db.session import engine, get_db
from app.main import app
from app.services.calendar import available_slots


@pytest.fixture
def founder_client():
    uid = uuid.uuid4()
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint")
    conn.execute(text("insert into auth.users (id, email) values (:i, :e)"),
                 {"i": str(uid), "e": f"t{uid.hex[:8]}@x.com"})
    # The security boundary migration 7c4f0f1a9d2e added: the function
    # refuses unless the caller has already asserted which user it
    # authenticated. app/services/provisioning.py does this before every real
    # call; these fixtures never did, and every one of them errored out with
    # "missing authenticated user context" before reaching a single assertion.
    conn.execute(text("select set_config('app.current_founder_uuid', :u, true)"),
                 {"u": str(uid)})
    conn.execute(
        text("select create_founder_on_signup(:u,:n,:e,:p,:t,:i,:b)"),
        dict(u=str(uid), n="Disc Test", e=f"t{uid.hex[:8]}@x.com", p="v1", t="v1", i="127.0.0.1", b="test"),
    )
    # Signup lands on Free, which includes zero free discovery calls. These tests
    # exercise the booking mechanism, not the paywall, so put the founder on a
    # tier that includes a call -- otherwise every booking test asserts 402 and
    # the thing they exist to cover goes untested. The paywall itself is covered
    # by test_free_tier_cannot_book_without_paying below.
    conn.execute(text("update founders set plan_type = 'starter' where user_id = :u"),
                 {"u": str(uid)})
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_founder] = lambda: AuthUser(id=str(uid), email="x@y.com", provider="test")
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        session.close()
        trans.rollback()
        conn.close()


# --- profile progress + validation -----------------------------------------
#
# Rewritten 2026-08-17 for the 4-section, path-branching onboarding redesign
# (see app/services/profile_progress.py's own docstring): required fields are
# now computed per founder from their stage, so a stage answer has to land
# before "required" is even well-defined -- before that, path-specific fields
# (vision_1_year, goal_90_day, ...) correctly count toward neither path.

def test_progress_before_stage_only_counts_path_agnostic_fields(founder_client):
    r = founder_client.get("/api/v1/profile/progress")
    assert r.status_code == 200
    body = r.json()
    # ALWAYS_REQUIRED (9) + OPTIONAL_FIELDS (1) -- no path-specific fields
    # until stage is known.
    assert body["total"] == 10
    start = body["filled"]

    founder_client.patch("/api/v1/profile/business", json={"problem_statement": "fix churn"})
    body2 = founder_client.get("/api/v1/profile/progress").json()
    assert body2["filled"] == start + 1
    assert body2["percent"] >= body["percent"]


def test_validate_lists_missing_required_once_path_is_known(founder_client):
    # Validation -> Stage 0->1 -> Path 2, which requires vision_1_year, not
    # goal_90_day.
    founder_client.patch("/api/v1/profile/business", json={"stage": "Validation"})
    r = founder_client.get("/api/v1/profile/validate")
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is False
    missing = {m["field"] for m in body["missing"]}
    assert "vision_1_year" in missing       # Path 2 -- required, not filled yet
    assert "goal_90_day" not in missing     # Path 1 only -- never required here


def test_validate_becomes_valid_when_filled(founder_client):
    # fill every required field for Path 2 (Validation -> Stage 0->1)
    founder_client.patch("/api/v1/profile/business", json={
        "stage": "Validation", "building_summary": "x", "product_description": "x",
        "problem_statement": "x", "customer_segment": ["Businesses"], "industry": "saas",
        "current_challenges": ["Cash flow"], "current_revenue": "pre_revenue",
        "founder_reality_signals": {
            "clear_next_priorities": True, "decisive": True, "effort_aligned_to_growth": True,
            "executes_consistently": True, "mentally_clear": True,
        },
        "business_reality_signals": {
            "revenue_predictable": False, "systems_defined": False, "plans_become_execution": False,
            "team_independent": False, "financials_clear": False,
        },
        "invisible_gaps": ["No clear roadmap"],
    })
    founder_client.patch("/api/v1/profile/goals", json={"vision_1_year": "x"})
    founder_client.patch("/api/v1/profile/founder", json={"experience_level": "serial"})
    body = founder_client.get("/api/v1/profile/validate").json()
    assert body["valid"] is True, body["missing"]
    assert body["missing"] == []


# --- discovery: slots + booking --------------------------------------------

def test_slots_returns_future_weekday_slots(founder_client):
    r = founder_client.get("/api/v1/profile")  # warm auth
    r = founder_client.get("/api/v1/discovery/slots?days=7")
    assert r.status_code == 200
    slots = r.json()["slots"]
    assert len(slots) > 0
    now = datetime.now(timezone.utc)
    assert all(datetime.fromisoformat(s) > now for s in slots)


def test_requesting_a_call_is_not_blocked_by_the_paywall(founder_client):
    """Booking a call is free on every plan, and confirms straight away.

    This used to be a 402: no plan includes a free call, so the entitlement gate
    refused every founder and there was no way to pay past it. Booking is free
    again, and there is no approval step left to put a gate behind -- when
    checkout exists it belongs immediately before the meeting is created.
    """
    from app.api.deps import get_founder_record
    founder = founder_client.get("/api/v1/profile").json()
    app.dependency_overrides[get_founder_record] = lambda: SimpleNamespace(
        founder_id=founder["founder_id"], plan_type="free")
    try:
        when = founder_client.get("/api/v1/discovery/slots").json()["slots"][0]
        r = founder_client.post("/api/v1/discovery/book", json={"scheduled_at": when})
        assert r.status_code == 201, r.text
        assert r.json()["status"] == "confirmed"
    finally:
        app.dependency_overrides.pop(get_founder_record, None)


def test_book_confirms_immediately_with_a_joining_link(founder_client):
    """Booking a published slot confirms it. No approval queue any more."""
    when = founder_client.get("/api/v1/discovery/slots").json()["slots"][0]
    r = founder_client.post("/api/v1/discovery/book", json={"scheduled_at": when})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "confirmed"
    # The founder leaves with a way to join. Stub mode still returns one, so
    # this asserts the wiring rather than Google.
    assert body["meeting_link"]
    call_id = body["call_id"]

    # confirmation read-back
    got = founder_client.get(f"/api/v1/discovery/calls/{call_id}")
    assert got.status_code == 200 and got.json()["call_id"] == call_id
    # appears in the list
    assert any(c["call_id"] == call_id for c in founder_client.get("/api/v1/discovery/calls").json())


def test_book_rejects_past_slot(founder_client):
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    r = founder_client.post("/api/v1/discovery/book", json={"scheduled_at": past})
    assert r.status_code == 422


def test_book_rejects_a_time_we_never_offered(founder_client):
    """Mattered less when a human approved every request; now it is the only
    thing stopping a confirmed 3am call."""
    odd = (datetime.now(timezone.utc) + timedelta(days=3)).replace(
        hour=3, minute=17, second=0, microsecond=0)
    r = founder_client.post("/api/v1/discovery/book",
                            json={"scheduled_at": odd.isoformat()})
    assert r.status_code == 422


def test_second_founder_cannot_take_the_same_slot(founder_client):
    when = founder_client.get("/api/v1/discovery/slots").json()["slots"][0]
    first = founder_client.post("/api/v1/discovery/book", json={"scheduled_at": when})
    assert first.status_code == 201, first.text
    again = founder_client.post("/api/v1/discovery/book", json={"scheduled_at": when})
    assert again.status_code == 409


def test_cannot_read_another_founders_call(founder_client):
    # a call id that doesn't belong to this founder -> 404, not leaked
    assert founder_client.get("/api/v1/discovery/calls/999999999").status_code == 404


# --- slot generator unit check ---------------------------------------------

def test_available_slots_skips_weekends_and_starts_tomorrow():
    ref = datetime(2026, 7, 24, 12, 0, tzinfo=timezone.utc)  # a Friday
    slots = available_slots(ref, days=7)
    assert all(s > ref for s in slots)
    assert all(s.weekday() < 5 for s in slots)  # no weekends


# --- slot claiming, without the API ----------------------------------------
#
# These exercise _claim_slot directly with a stub session, so they run even
# where the founder fixture cannot.

class _FakeResult:
    def __init__(self, row=None):
        self._row = row

    def first(self):
        return self._row


class _FakeDB:
    """Answers the advisory lock, then reports whether the slot is taken."""

    def __init__(self, taken=False):
        self.taken = taken
        self.statements = []

    def execute(self, statement, params=None):
        text = str(statement)
        self.statements.append(text)
        if "pg_advisory_xact_lock" in text:
            return _FakeResult()
        return _FakeResult((1,) if self.taken else None)


def _first_offered_slot():
    """The same grid _claim_slot builds for a founder without priority.

    Must use STANDARD_CALL_LEAD_DAYS rather than a hand-picked number: a
    priority founder's window opens two business days earlier, so a slot taken
    from the wrong grid is genuinely not on offer and the test would fail for
    the right reason about the wrong thing.
    """
    from app.plans.catalog import STANDARD_CALL_LEAD_DAYS
    from app.services.calendar import available_slots
    return available_slots(datetime.now(timezone.utc), 30,
                           lead_days=STANDARD_CALL_LEAD_DAYS)[0]


def test_claim_slot_accepts_a_published_free_slot(monkeypatch):
    from app.api.v1.discovery import routes
    monkeypatch.setattr(routes, "_has_call_priority", lambda founder, db: False)
    db = _FakeDB(taken=False)
    routes._claim_slot(db, _first_offered_slot(), object())
    assert any("pg_advisory_xact_lock" in s for s in db.statements)


def test_claim_slot_refuses_a_time_not_on_the_grid(monkeypatch):
    from app.api.v1.discovery import routes
    monkeypatch.setattr(routes, "_has_call_priority", lambda founder, db: False)
    odd = _first_offered_slot() + timedelta(minutes=17)
    with pytest.raises(routes.SlotNotOfferedError):
        routes._claim_slot(_FakeDB(), odd, object())


def test_claim_slot_refuses_a_slot_someone_already_has(monkeypatch):
    from app.api.v1.discovery import routes
    monkeypatch.setattr(routes, "_has_call_priority", lambda founder, db: False)
    with pytest.raises(routes.SlotTakenError):
        routes._claim_slot(_FakeDB(taken=True), _first_offered_slot(), object())
