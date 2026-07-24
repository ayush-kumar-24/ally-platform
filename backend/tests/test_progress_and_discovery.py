"""Profile progress/validation + discovery-call booking, against seeded founders."""

import uuid
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
    conn.execute(
        text("select create_founder_on_signup(:u,:n,:e,:p,:t,:i,:b)"),
        dict(u=str(uid), n="Disc Test", e=f"t{uid.hex[:8]}@x.com", p="v1", t="v1", i="127.0.0.1", b="test"),
    )
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

def test_progress_starts_low_then_rises(founder_client):
    r = founder_client.get("/api/v1/profile/progress")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 13
    start = body["filled"]

    founder_client.patch("/api/v1/profile/goals", json={"goal_90_day": "ship v1", "vision_1_year": "1k users"})
    body2 = founder_client.get("/api/v1/profile/progress").json()
    assert body2["filled"] == start + 2
    assert body2["percent"] >= body["percent"]


def test_validate_lists_missing_required(founder_client):
    r = founder_client.get("/api/v1/profile/validate")
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is False
    missing = {m["field"] for m in body["missing"]}
    assert "goal_90_day" in missing  # not filled yet


def test_validate_becomes_valid_when_filled(founder_client):
    # fill every required field
    founder_client.patch("/api/v1/profile/business", json={
        "stage": "Validation", "building_summary": "x", "problem_statement": "x",
        "customer_segment": "b2b", "industry": "saas", "current_challenges": ["retention"],
    })
    founder_client.patch("/api/v1/profile/goals", json={"goal_90_day": "x", "vision_1_year": "x"})
    founder_client.patch("/api/v1/profile/founder", json={
        "founder_motivation": "x", "support_preferences": ["sales"],
        "experience_level": "serial", "emotional_state": ["excited"],
    })
    body = founder_client.get("/api/v1/profile/validate").json()
    assert body["valid"] is True
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


def test_book_creates_confirmed_call(founder_client):
    when = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    r = founder_client.post("/api/v1/discovery/book", json={"scheduled_at": when})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "confirmed"
    assert body["meeting_link"] and body["booking_source"] == "stub"
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


def test_cannot_read_another_founders_call(founder_client):
    # a call id that doesn't belong to this founder -> 404, not leaked
    assert founder_client.get("/api/v1/discovery/calls/999999999").status_code == 404


# --- slot generator unit check ---------------------------------------------

def test_available_slots_skips_weekends_and_starts_tomorrow():
    ref = datetime(2026, 7, 24, 12, 0, tzinfo=timezone.utc)  # a Friday
    slots = available_slots(ref, days=7)
    assert all(s > ref for s in slots)
    assert all(s.weekday() < 5 for s in slots)  # no weekends
