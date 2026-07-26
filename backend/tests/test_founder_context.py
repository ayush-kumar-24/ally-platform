"""Founder context ("memory") CRUD, against a seeded founder (rolled back)."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.auth import AuthUser, get_current_founder
from app.db.session import engine, get_db
from app.main import app

URL = "/api/v1/profile/context"


@pytest.fixture
def founder_client():
    uid = uuid.uuid4()
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint")
    conn.execute(text("insert into auth.users (id, email) values (:i, :e)"),
                 {"i": str(uid), "e": f"t{uid.hex[:8]}@x.com"})
    conn.execute(text("select create_founder_on_signup(:u,:n,:e,:p,:t,:i,:b)"),
                 dict(u=str(uid), n="Ctx Test", e=f"t{uid.hex[:8]}@x.com", p="v1", t="v1", i="127.0.0.1", b="supabase"))
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_founder] = lambda: AuthUser(id=str(uid), email="x@y.com", provider="supabase")
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        session.close()
        trans.rollback()
        conn.close()


def test_empty_context_when_none_set(founder_client):
    r = founder_client.get(URL)
    assert r.status_code == 200
    assert r.json()["geographic_type"] is None


def test_upsert_creates_then_updates(founder_client):
    # create
    r = founder_client.put(URL, json={"geographic_type": "metro", "network_access": "strong"})
    assert r.status_code == 200
    assert r.json()["geographic_type"] == "metro"

    # read back
    assert founder_client.get(URL).json()["network_access"] == "strong"

    # partial update keeps the other field
    r = founder_client.put(URL, json={"economic_background": "salaried"})
    assert r.status_code == 200
    body = r.json()
    assert body["economic_background"] == "salaried"
    assert body["geographic_type"] == "metro"   # survived


def test_rejects_invalid_enum(founder_client):
    r = founder_client.put(URL, json={"geographic_type": "moon_base"})
    assert r.status_code == 422


def test_rejects_unknown_field(founder_client):
    r = founder_client.put(URL, json={"favourite_colour": "blue"})
    assert r.status_code == 422
