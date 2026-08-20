"""API tests for the Framework Usage endpoints. dependency_overrides inject
an in-memory service + a fake founder; no DB/auth backend."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.v1.framework_usage.dependencies import get_current_founder_id, get_framework_usage_service
from app.framework_usage import InMemoryFrameworkUsageRepository, build_framework_usage_service
from app.main import app

BASE = "/api/v1/frameworks"
T0 = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)


class StepClock:
    def __init__(self, start=T0, step=timedelta(seconds=1)):
        self._now, self._step = start, step

    def __call__(self):
        v = self._now
        self._now += self._step
        return v


@pytest.fixture
def client():
    repo = InMemoryFrameworkUsageRepository()
    service = build_framework_usage_service(repo, clock=StepClock())
    founder = {"id": 1}
    app.dependency_overrides[get_current_founder_id] = lambda: founder["id"]
    app.dependency_overrides[get_framework_usage_service] = lambda: service
    http = TestClient(app)
    http.founder = founder
    yield http
    for dep in (get_current_founder_id, get_framework_usage_service):
        app.dependency_overrides.pop(dep, None)


# --- GET /frameworks/usage -----------------------------------------------


def test_get_usage_empty_for_new_founder(client):
    assert client.get(f"{BASE}/usage").json() == {}


def test_get_usage_reflects_recorded_frameworks(client):
    client.post(f"{BASE}/first-principles/use")
    client.post(f"{BASE}/swot/use")
    body = client.get(f"{BASE}/usage").json()
    assert set(body.keys()) == {"first-principles", "swot"}
    assert body["first-principles"]["note"] == ""


# --- POST /frameworks/{id}/use ------------------------------------------


def test_record_used_200(client):
    r = client.post(f"{BASE}/first-principles/use")
    assert r.status_code == 200
    body = r.json()
    assert body["framework_id"] == "first-principles"
    assert body["note"] == ""
    assert body["last_used_at"] is not None


def test_record_used_again_bumps_timestamp(client):
    first = client.post(f"{BASE}/swot/use").json()
    second = client.post(f"{BASE}/swot/use").json()
    assert second["last_used_at"] > first["last_used_at"]


def test_record_used_keeps_existing_note(client):
    client.post(f"{BASE}/swot/use")
    client.put(f"{BASE}/swot/note", json={"note": "Used on the pricing pivot."})
    updated = client.post(f"{BASE}/swot/use").json()
    assert updated["note"] == "Used on the pricing pivot."


# --- PUT /frameworks/{id}/note --------------------------------------------


def test_save_note_200(client):
    client.post(f"{BASE}/okrs/use")
    r = client.put(f"{BASE}/okrs/note", json={"note": "Set quarterly OKRs with the team."})
    assert r.status_code == 200
    assert r.json()["note"] == "Set quarterly OKRs with the team."


def test_save_note_clears_on_blank(client):
    client.post(f"{BASE}/okrs/use")
    client.put(f"{BASE}/okrs/note", json={"note": "a note"})
    r = client.put(f"{BASE}/okrs/note", json={"note": "   "})
    assert r.json()["note"] == ""


def test_save_note_unknown_field_rejected(client):
    r = client.put(f"{BASE}/okrs/note", json={"note": "ok", "founder_id": 999})
    assert r.status_code == 422


def test_save_note_overlong_rejected(client):
    r = client.put(f"{BASE}/okrs/note", json={"note": "x" * 2001})
    assert r.status_code == 422


# --- isolation ------------------------------------------------------------


def test_founder_isolation(client):
    client.post(f"{BASE}/first-principles/use")
    client.founder["id"] = 2
    assert client.get(f"{BASE}/usage").json() == {}
