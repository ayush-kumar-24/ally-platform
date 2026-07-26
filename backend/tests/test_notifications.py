"""In-app notifications feed, against a seeded founder + notifications (rolled back)."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.auth import AuthUser, get_current_founder
from app.db.session import engine, get_db
from app.main import app

BASE = "/api/v1/notifications"


def _add_notification(conn, fid, title, *, channel="in_app", is_read=False):
    conn.execute(text(
        "insert into notifications (founder_id, type, channel, title, body, is_read) "
        "values (:f, 'product_update', :c, :t, 'body text', :r)"
    ), {"f": fid, "c": channel, "t": title, "r": is_read})


@pytest.fixture
def founder_client():
    uid = uuid.uuid4()
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint")
    conn.execute(text("insert into auth.users (id, email) values (:i, :e)"),
                 {"i": str(uid), "e": f"t{uid.hex[:8]}@x.com"})
    fid = conn.execute(text("select create_founder_on_signup(:u,:n,:e,:p,:t,:i,:b)"),
                       dict(u=str(uid), n="Notif Test", e=f"t{uid.hex[:8]}@x.com",
                            p="v1", t="v1", i="127.0.0.1", b="supabase")).scalar()
    # 2 unread in-app, 1 read in-app, 1 email-channel (must NOT appear in the feed)
    _add_notification(conn, fid, "Unread one")
    _add_notification(conn, fid, "Unread two")
    _add_notification(conn, fid, "Already read", is_read=True)
    _add_notification(conn, fid, "Email only", channel="email")

    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_founder] = lambda: AuthUser(id=str(uid), email="x@y.com", provider="supabase")
    try:
        yield TestClient(app), fid
    finally:
        app.dependency_overrides.clear()
        session.close()
        trans.rollback()
        conn.close()


def test_list_shows_in_app_only_with_unread_count(founder_client):
    client, _ = founder_client
    r = client.get(BASE)
    assert r.status_code == 200
    body = r.json()
    titles = [n["title"] for n in body["items"]]
    assert "Email only" not in titles          # email channel excluded from the feed
    assert len(body["items"]) == 3             # 3 in-app
    assert body["unread_count"] == 2           # 2 unread


def test_unread_only_filter(founder_client):
    client, _ = founder_client
    body = client.get(f"{BASE}?unread_only=true").json()
    assert len(body["items"]) == 2
    assert all(n["is_read"] is False for n in body["items"])


def test_mark_one_read(founder_client):
    client, _ = founder_client
    first_unread = client.get(f"{BASE}?unread_only=true").json()["items"][0]
    nid = first_unread["notification_id"]

    r = client.post(f"{BASE}/{nid}/read")
    assert r.status_code == 200
    assert r.json()["is_read"] is True and r.json()["read_at"] is not None
    # unread count dropped by one
    assert client.get(BASE).json()["unread_count"] == 1


def test_mark_all_read(founder_client):
    client, _ = founder_client
    r = client.post(f"{BASE}/read-all")
    assert r.status_code == 200
    assert r.json()["marked_read"] == 2
    assert client.get(BASE).json()["unread_count"] == 0


def test_cannot_read_another_founders_notification(founder_client):
    client, _ = founder_client
    assert client.post(f"{BASE}/999999999/read").status_code == 404
