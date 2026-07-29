"""API tests for the settings-preferences endpoints (Phase 11).

Uses dependency_overrides: an in-memory-backed SettingsService + a fake authenticated
founder, so no DB or auth backend is needed. Business logic is covered by
test_settings_service.py.
"""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_founder_record
from app.api.v1.settings.dependencies import get_settings_service
from app.settings import DEFAULT_SESSION_TIMEOUT_MINUTES, build_settings_service

BASE = "/api/v1/settings"


@pytest.fixture
def client():
    service = build_settings_service()               # in-memory, shared across the test
    founder = {"id": 1}
    app.dependency_overrides[get_founder_record] = lambda: SimpleNamespace(founder_id=founder["id"])
    app.dependency_overrides[get_settings_service] = lambda: service
    yield SimpleNamespace(http=TestClient(app), founder=founder, service=service)
    app.dependency_overrides.pop(get_founder_record, None)
    app.dependency_overrides.pop(get_settings_service, None)


def test_get_preferences_creates_defaults(client):
    r = client.http.get(f"{BASE}/preferences")
    assert r.status_code == 200
    body = r.json()
    assert body["founder_id"] == 1
    assert body["reminders"]["reminder_time"] == "09:00"
    assert body["security"]["session_timeout_minutes"] == DEFAULT_SESSION_TIMEOUT_MINUTES


def test_patch_reminders(client):
    r = client.http.patch(f"{BASE}/reminders", json={"reminder_time": "07:30", "daily_reminders": False})
    assert r.status_code == 200 and r.json()["reminder_time"] == "07:30"
    assert client.http.get(f"{BASE}/preferences").json()["reminders"]["daily_reminders"] is False


def test_patch_security(client):
    r = client.http.patch(f"{BASE}/security", json={"session_timeout_minutes": 30})
    assert r.status_code == 200 and r.json()["session_timeout_minutes"] == 30


def test_reset_endpoint(client):
    client.http.patch(f"{BASE}/reminders", json={"reminder_time": "06:00"})
    client.http.patch(f"{BASE}/security", json={"session_timeout_minutes": 15})
    r = client.http.post(f"{BASE}/reset")
    assert r.status_code == 200
    assert r.json()["reminders"]["reminder_time"] == "09:00"
    assert r.json()["security"]["session_timeout_minutes"] == DEFAULT_SESSION_TIMEOUT_MINUTES


def test_invalid_reminder_time_422(client):
    assert client.http.patch(f"{BASE}/reminders", json={"reminder_time": "99:99"}).status_code == 422


def test_invalid_session_timeout_422(client):
    assert client.http.patch(f"{BASE}/security", json={"session_timeout_minutes": 0}).status_code == 422


def test_unknown_field_rejected_422(client):
    assert client.http.patch(f"{BASE}/reminders", json={"nope": True}).status_code == 422


def test_founder_isolation(client):
    client.http.patch(f"{BASE}/reminders", json={"reminder_time": "05:00"})     # founder 1
    client.founder["id"] = 2
    body = client.http.get(f"{BASE}/preferences").json()
    assert body["founder_id"] == 2 and body["reminders"]["reminder_time"] == "09:00"   # fresh defaults


def test_error_shape_consistent(client):
    r = client.http.patch(f"{BASE}/reminders", json={"reminder_time": "bad"})
    assert r.status_code == 422 and set(r.json()) >= {"error", "message", "request_id"}
