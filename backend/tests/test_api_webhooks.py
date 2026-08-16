"""API tests for inbound webhooks. The DB session and container calls are stubbed
(monkeypatched) rather than hitting a real database -- these tests are about the
transport (secret auth, payload handling, response shape), not the SQL repository,
which is covered indirectly via test_privacy_executor.py's contract tests."""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.session import get_db
from app.main import app
from app.privacy.deletion_repository import DeletionOutcome

BASE = "/api/v1/webhooks"
SECRET = "test-webhook-secret"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_WEBHOOK_SECRET", SECRET)
    app.dependency_overrides[get_db] = lambda: SimpleNamespace()
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)


def _headers(secret=SECRET):
    return {"X-Webhook-Secret": secret} if secret is not None else {}


# --- auth --------------------------------------------------------------------


def test_missing_secret_rejected(client):
    r = client.post(f"{BASE}/deletion-sweep", headers=_headers(None))
    assert r.status_code == 401


def test_wrong_secret_rejected(client):
    r = client.post(f"{BASE}/deletion-sweep", headers=_headers("wrong"))
    assert r.status_code == 401


def test_unconfigured_secret_fails_closed(client, monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_WEBHOOK_SECRET", "")
    r = client.post(f"{BASE}/deletion-sweep", headers=_headers(SECRET))
    assert r.status_code == 401


# --- deletion-sweep ------------------------------------------------------------


def test_deletion_sweep_runs_the_executor(client, monkeypatch):
    from app.privacy.executor import ExecutionSummary

    summary = ExecutionSummary(
        checked=2,
        succeeded=[DeletionOutcome(founder_id=1, deletion_id=10, completed_at=None)],
        failed=[DeletionOutcome(founder_id=2, deletion_id=11, error="boom")],
    )
    fake_executor = SimpleNamespace(run_due=lambda batch_size=50: summary)
    monkeypatch.setattr("app.api.v1.webhooks.router.container.deletion_executor",
                        lambda db: fake_executor)

    r = client.post(f"{BASE}/deletion-sweep", headers=_headers())

    assert r.status_code == 200
    body = r.json()
    assert body == {"checked": 2, "succeeded": 1, "failed": 1, "failed_founder_ids": [2]}


# --- auth-user-deleted ----------------------------------------------------------


def test_auth_user_deleted_erases_the_matching_founder(client, monkeypatch):
    founder = SimpleNamespace(founder_id=42)
    monkeypatch.setattr("app.api.v1.webhooks.router._founders.get_by_user_id",
                        lambda db, uid: founder)
    outcome = DeletionOutcome(founder_id=42, deletion_id=5, data_types_deleted={"x": 1},
                              completed_at=None)
    fake_executor = SimpleNamespace(execute_now=lambda fid: outcome)
    monkeypatch.setattr("app.api.v1.webhooks.router.container.deletion_executor",
                        lambda db: fake_executor)

    r = client.post(f"{BASE}/supabase/auth-user-deleted", headers=_headers(),
                    json={"type": "DELETE", "table": "users", "schema": "auth",
                          "record": None, "old_record": {"id": "11111111-1111-1111-1111-111111111111"}})

    assert r.status_code == 200
    body = r.json()
    assert body == {"handled": True, "founder_id": 42, "succeeded": True,
                    "data_types_deleted": {"x": 1}, "error": None}


def test_auth_user_deleted_no_matching_founder(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.webhooks.router._founders.get_by_user_id",
                        lambda db, uid: None)

    r = client.post(f"{BASE}/supabase/auth-user-deleted", headers=_headers(),
                    json={"type": "DELETE", "old_record": {"id": "not-a-real-user"}})

    assert r.status_code == 200
    assert r.json()["handled"] is False


def test_auth_user_deleted_without_old_record_acknowledged_not_erased(client):
    r = client.post(f"{BASE}/supabase/auth-user-deleted", headers=_headers(),
                    json={"type": "INSERT", "record": {"id": "x"}})
    assert r.status_code == 200
    assert r.json()["handled"] is False
