"""API tests for the Privacy Center. dependency_overrides inject an in-memory
service + a fake founder; no DB/auth backend."""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.v1.privacy.dependencies import get_current_founder_id, get_privacy_service
from app.consents import build_consent_service
from app.main import app
from app.privacy import InMemoryPrivacyRepository, build_privacy_service

BASE = "/api/v1/privacy"
T0 = datetime(2026, 8, 2, 12, 0, 0, tzinfo=timezone.utc)
YES = {"confirm": True}


@pytest.fixture
def client():
    consents = build_consent_service(clock=lambda: T0)
    repo = InMemoryPrivacyRepository({"founder_profile": [{"founder_id": 1}], "plans": [{"p": 1}]})
    service = build_privacy_service(repo, clock=lambda: T0, consent_service=consents)
    founder = {"id": 1}
    app.dependency_overrides[get_current_founder_id] = lambda: founder["id"]
    app.dependency_overrides[get_privacy_service] = lambda: service
    yield SimpleNamespace(http=TestClient(app), founder=founder, service=service, consents=consents)
    for dep in (get_current_founder_id, get_privacy_service):
        app.dependency_overrides.pop(dep, None)


# --- GET /privacy/export ----------------------------------------------------


def test_export_200(client):
    r = client.http.get(f"{BASE}/export")
    assert r.status_code == 200
    body = r.json()
    assert body["founder_id"] == 1 and body["record_count"] == 2
    assert set(body["sections"]) == {"founder_profile", "plans"}
    assert body["request"]["request_type"] == "download_data"
    assert body["kind"] == "access"


def test_export_portability_is_a_different_request(client):
    """?kind=portability exercises Art 20, not Art 15. The two buttons in the
    Privacy Center used to call one endpoint and download identical files."""
    r = client.http.get(f"{BASE}/export?kind=portability")
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "portability"
    assert body["request"]["request_type"] == "portability"


def test_export_rejects_an_unknown_kind(client):
    r = client.http.get(f"{BASE}/export?kind=everything")
    assert r.status_code == 422


# --- DELETE /privacy/account ------------------------------------------------


def test_delete_account_schedules(client):
    r = client.http.request("DELETE", f"{BASE}/account", json=YES)
    assert r.status_code == 200
    body = r.json()
    assert body["state"]["deletion_pending"] is True
    assert body["state"]["deletion_scheduled_at"].startswith("2026-09-01")
    assert "scheduled" in body["message"].lower()


def test_delete_account_requires_confirmation(client):
    r = client.http.request("DELETE", f"{BASE}/account", json={"confirm": False})
    assert r.status_code == 422
    assert client.http.get(f"{BASE}/status").json()["state"]["deletion_pending"] is False


def test_delete_account_twice_409(client):
    client.http.request("DELETE", f"{BASE}/account", json=YES)
    assert client.http.request("DELETE", f"{BASE}/account", json=YES).status_code == 409


# --- POST /privacy/withdraw -------------------------------------------------


def test_withdraw_pauses_processing(client):
    r = client.http.post(f"{BASE}/withdraw", json=YES)
    assert r.status_code == 200
    body = r.json()
    assert body["state"]["processing_restricted"] is True
    assert body["state"]["deletion_pending"] is False       # not an erasure


def test_withdraw_requires_confirmation(client):
    assert client.http.post(f"{BASE}/withdraw", json={"confirm": False}).status_code == 422


def test_withdraw_updates_consent_ledger(client):
    client.consents.record_consent(1, terms_version="1.0", privacy_version="1.0",
                                   agree_terms=True, agree_diagnosis=True)
    client.http.post(f"{BASE}/withdraw", json=YES)
    assert client.consents.get_current(1).agree_diagnosis is False


# --- POST /privacy/restrict -------------------------------------------------


def test_restrict_and_resume(client):
    on = client.http.post(f"{BASE}/restrict", json={"restricted": True})
    assert on.status_code == 200 and on.json()["state"]["processing_restricted"] is True

    off = client.http.post(f"{BASE}/restrict", json={"restricted": False})
    assert off.json()["state"]["processing_restricted"] is False
    assert "resume" in off.json()["message"].lower()


def test_restrict_defaults_to_true(client):
    assert client.http.post(f"{BASE}/restrict", json={}).json()["state"]["processing_restricted"] is True


def test_restrict_rejects_unknown_field(client):
    assert client.http.post(f"{BASE}/restrict", json={"nope": 1}).status_code == 422


# --- GET /privacy/status ----------------------------------------------------


def test_status_lists_history(client):
    client.http.get(f"{BASE}/export")
    client.http.post(f"{BASE}/restrict", json={"restricted": True})
    body = client.http.get(f"{BASE}/status").json()
    assert body["total"] == 2
    assert body["state"]["processing_restricted"] is True
    assert [r["request_type"] for r in body["requests"]] == ["restrict_processing", "download_data"]


def test_founder_isolation(client):
    client.http.post(f"{BASE}/restrict", json={"restricted": True})
    client.founder["id"] = 2
    body = client.http.get(f"{BASE}/status").json()
    assert body["state"]["processing_restricted"] is False and body["total"] == 0
