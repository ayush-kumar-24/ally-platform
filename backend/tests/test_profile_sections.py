"""Section endpoints (founder / business / goals) + provisioning.

Drives the real endpoints against a founder seeded inside a rolled-back
transaction, so nothing persists.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.auth import AuthUser, get_current_founder
from app.db.session import engine, get_db
from app.main import app
from app.services.provisioning import ensure_founder

BASE = "/api/v1/profile"


@pytest.fixture
def founder_client():
    """A client authenticated as a freshly-seeded founder; all rolled back."""
    uid = uuid.uuid4()
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint")
    conn.execute(text("insert into auth.users (id, email) values (:i, :e)"),
                 {"i": str(uid), "e": f"t{uid.hex[:8]}@x.com"})
    fid = conn.execute(
        text("select create_founder_on_signup(:u,:n,:e,:p,:t,:i,:b)"),
        dict(u=str(uid), n="Sec Test", e=f"t{uid.hex[:8]}@x.com", p="v1", t="v1", i="127.0.0.1", b="test"),
    ).scalar()

    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_founder] = lambda: AuthUser(id=str(uid), email="x@y.com", provider="test")
    try:
        yield TestClient(app), uid
    finally:
        app.dependency_overrides.clear()
        session.close()
        trans.rollback()
        conn.close()


def test_founder_section_update_and_read(founder_client):
    client, _ = founder_client
    r = client.patch(f"{BASE}/founder", json={
        "founder_motivation": "to fix churn",
        "support_preferences": ["sales", "hiring"],
        "experience_level": "serial",
        "emotional_state": ["determined", "hopeful"],
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["support_preferences"] == ["sales", "hiring"]
    assert body["emotional_state"] == ["determined", "hopeful"]
    # read back
    assert client.get(f"{BASE}/founder").json()["founder_motivation"] == "to fix churn"


def test_founder_section_rejects_invalid_feeling(founder_client):
    client, _ = founder_client
    r = client.patch(f"{BASE}/founder", json={"emotional_state": ["angry"]})
    assert r.status_code == 422  # not one of the 8 allowed feelings


def test_founder_section_rejects_foreign_field(founder_client):
    client, _ = founder_client
    # goal_90_day belongs to /goals, not /founder
    r = client.patch(f"{BASE}/founder", json={"goal_90_day": "x"})
    assert r.status_code == 422


def test_business_section_resolves_stage_name(founder_client):
    client, _ = founder_client
    r = client.patch(f"{BASE}/business", json={
        "stage": "Validation",
        "building_summary": "an AI copilot",
        "current_challenges": ["retention"],
    })
    assert r.status_code == 200, r.text
    assert r.json()["stage_id"] == 2          # Validation -> stage_id 2
    assert r.json()["building_summary"] == "an AI copilot"


def test_business_section_rejects_bad_stage(founder_client):
    client, _ = founder_client
    r = client.patch(f"{BASE}/business", json={"stage": "Plateau"})
    assert r.status_code == 422


def test_goals_section(founder_client):
    client, _ = founder_client
    r = client.patch(f"{BASE}/goals", json={"goal_90_day": "ship v1", "vision_1_year": "1000 users"})
    assert r.status_code == 200
    assert r.json() == {"goal_90_day": "ship v1", "vision_1_year": "1000 users"}


def test_partial_update_leaves_other_fields(founder_client):
    client, _ = founder_client
    client.patch(f"{BASE}/founder", json={"founder_motivation": "keep me"})
    client.patch(f"{BASE}/goals", json={"goal_90_day": "unrelated"})
    # the founder-section field survived a goals update
    assert client.get(f"{BASE}/founder").json()["founder_motivation"] == "keep me"


# --- provisioning -----------------------------------------------------------

def test_provisioning_is_idempotent(founder_client):
    _, uid = founder_client
    # a second ensure_founder for the same identity returns the existing row, no dup
    conn = engine.connect(); trans = conn.begin(); session = Session(bind=conn)
    try:
        session.execute(text("insert into auth.users (id, email) values (:i, :e)"),
                        {"i": str(uid_2 := uuid.uuid4()), "e": f"t{uid_2.hex[:8]}@x.com"})
        ident = AuthUser(id=str(uid_2), email=f"t{uid_2.hex[:8]}@x.com", provider="supabase")
        f1 = ensure_founder(ident, session)
        f2 = ensure_founder(ident, session)
        assert f1 is not None and f1.founder_id == f2.founder_id
    finally:
        session.close(); trans.rollback(); conn.close()


def test_dev_identity_not_provisioned():
    conn = engine.connect(); trans = conn.begin(); session = Session(bind=conn)
    try:
        ident = AuthUser(id="00000000-0000-0000-0000-000000000001", email="dev@ally.local", provider="dev")
        assert ensure_founder(ident, session) is None  # dev never provisions
    finally:
        session.close(); trans.rollback(); conn.close()
