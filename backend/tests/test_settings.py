"""Settings & notifications endpoints, against a seeded founder (rolled back)."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.auth import AuthUser, get_current_founder
from app.db.session import engine, get_db
from app.main import app

BASE = "/api/v1/settings"


@pytest.fixture
def founder_client():
    uid = uuid.uuid4()
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint")
    conn.execute(text("insert into auth.users (id, email) values (:i, :e)"),
                 {"i": str(uid), "e": f"t{uid.hex[:8]}@x.com"})
    conn.execute(text("select create_founder_on_signup(:u,:n,:e,:p,:t,:i,:b)"),
                 dict(u=str(uid), n="Set Test", e=f"t{uid.hex[:8]}@x.com", p="v1", t="v1", i="127.0.0.1", b="supabase"))
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_founder] = lambda: AuthUser(id=str(uid), email="x@y.com", provider="supabase")
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        session.close()
        trans.rollback()
        conn.close()


# --- overview + account -----------------------------------------------------

def test_overview_has_all_sections(founder_client):
    r = founder_client.get(BASE)
    assert r.status_code == 200
    body = r.json()
    assert body["account"]["full_name"] == "Set Test"
    assert body["security"]["auth_provider"] == "supabase"
    assert body["security"]["password_set"] is False
    assert "email_reminders" in body["notifications"]


def test_account_update_language(founder_client):
    r = founder_client.patch(f"{BASE}/account", json={"preferred_language": "hi"})
    assert r.status_code == 200
    assert r.json()["preferred_language"] == "hi"


def test_account_rejects_readonly_field(founder_client):
    # email is owned by auth, not editable here
    r = founder_client.patch(f"{BASE}/account", json={"email": "new@x.com"})
    assert r.status_code == 422


# --- notification preferences ----------------------------------------------

def test_notifications_default_on(founder_client):
    body = founder_client.get(f"{BASE}/notifications").json()
    assert body["email_reminders"] is True
    assert body["in_app_all"] is True


def test_notifications_partial_update_merges(founder_client):
    # turn off only email_reminders; the other toggles must survive
    r = founder_client.patch(f"{BASE}/notifications", json={"email_reminders": False})
    assert r.status_code == 200
    body = r.json()
    assert body["email_reminders"] is False
    assert body["in_app_all"] is True            # untouched
    assert body["email_report_ready"] is True    # untouched


def test_notifications_rejects_unknown_key(founder_client):
    r = founder_client.patch(f"{BASE}/notifications", json={"sms_alerts": True})
    assert r.status_code == 422


# --- security ---------------------------------------------------------------

def test_security_reports_social_login(founder_client):
    body = founder_client.get(f"{BASE}/security").json()
    assert body["login_method"] == "social"
    assert body["password_set"] is False
    assert body["auth_provider"] == "supabase"
