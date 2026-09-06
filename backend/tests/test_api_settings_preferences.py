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
from app.settings import build_settings_service

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
    assert body["security"]["login_notifications"] is True
    assert "reminders" not in body      # removed 2026-09-05


def test_patch_security(client):
    r = client.http.patch(f"{BASE}/security", json={"login_notifications": False})
    assert r.status_code == 200 and r.json()["login_notifications"] is False


def test_reset_endpoint(client):
    client.http.patch(f"{BASE}/security", json={"login_notifications": False})
    r = client.http.post(f"{BASE}/reset")
    assert r.status_code == 200
    assert r.json()["security"]["login_notifications"] is True


def test_retired_session_timeout_rejected_422(client):
    """session_timeout_minutes was removed on 2026-09-05 -- it had no consumer and
    no effect, so a founder setting it got a false assurance. `extra="forbid"`
    means a client still sending it now gets a clear 422 rather than silently
    writing a value nothing reads."""
    assert client.http.patch(f"{BASE}/security", json={"session_timeout_minutes": 30}).status_code == 422


def test_retired_meeting_reminders_rejected_422(client):
    """Same, for meeting_reminders -- it duplicated the Profile page's own
    "Call reminders by email" switch, which is the one that actually works."""
    assert client.http.patch(f"{BASE}/security", json={"meeting_reminders": False}).status_code == 422


def test_unknown_field_rejected_422(client):
    assert client.http.patch(f"{BASE}/security", json={"nope": True}).status_code == 422


def test_retired_reminders_endpoint_is_gone(client):
    """PATCH /settings/reminders went with the four reminder settings it wrote
    on 2026-09-05 -- none of them was read by anything.

    404, not 405: the path itself no longer exists on any method, rather than
    existing and refusing PATCH."""
    assert client.http.patch(f"{BASE}/reminders", json={"reminder_time": "07:30"}).status_code == 404


def test_founder_isolation(client):
    client.http.patch(f"{BASE}/security", json={"login_notifications": False})   # founder 1
    client.founder["id"] = 2
    body = client.http.get(f"{BASE}/preferences").json()
    # Founder 2 gets fresh defaults, untouched by founder 1's change.
    assert body["founder_id"] == 2 and body["security"]["login_notifications"] is True


def test_error_shape_consistent(client):
    r = client.http.patch(f"{BASE}/security", json={"login_notifications": "maybe"})
    assert r.status_code == 422 and set(r.json()) >= {"error", "message", "request_id"}
