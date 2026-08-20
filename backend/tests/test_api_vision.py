"""API tests for the Vision endpoints. dependency_overrides inject an
in-memory service + a fake founder; no DB/auth backend."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.v1.vision.dependencies import get_current_founder_id, get_vision_service
from app.main import app
from app.vision import InMemoryVisionRepository, build_vision_service

BASE = "/api/v1/vision"
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
    repo = InMemoryVisionRepository()
    service = build_vision_service(repo, clock=StepClock())
    founder = {"id": 1}
    app.dependency_overrides[get_current_founder_id] = lambda: founder["id"]
    app.dependency_overrides[get_vision_service] = lambda: service
    http = TestClient(app)
    http.founder = founder
    yield http
    for dep in (get_current_founder_id, get_vision_service):
        app.dependency_overrides.pop(dep, None)


# --- GET /vision -------------------------------------------------------


def test_get_vision_empty_shape_for_new_founder(client):
    body = client.get(BASE).json()
    assert set(body["territories"].keys()) == {"life", "business", "impact", "financial", "ideal_day", "legacy"}
    for t in body["territories"].values():
        assert t["statement"] == "" and t["tag1"] == "" and t["tag2"] == "" and t["updated_at"] is None
    assert body["summary"] == {"target": "", "current": "", "unit": "", "updated_at": None}


def test_get_vision_reflects_written_territory_and_summary(client):
    client.put(f"{BASE}/territories/business", json={"statement": "Runs without me.", "tag1": "4-day week", "tag2": ""})
    client.put(f"{BASE}/summary", json={"target": "₹100Cr"})
    body = client.get(BASE).json()
    assert body["territories"]["business"]["statement"] == "Runs without me."
    assert body["territories"]["life"]["statement"] == ""  # untouched
    assert body["summary"]["target"] == "₹100Cr"


# --- PUT /vision/territories/{key} --------------------------------------


def test_upsert_territory_200(client):
    r = client.put(f"{BASE}/territories/life", json={"statement": "My days are my own.", "tag1": "", "tag2": ""})
    assert r.status_code == 200
    body = r.json()
    assert body["territory"] == "life" and body["statement"] == "My days are my own."


def test_upsert_unknown_territory_422(client):
    r = client.put(f"{BASE}/territories/not-real", json={"statement": "x"})
    assert r.status_code == 422


def test_empty_statement_422(client):
    r = client.put(f"{BASE}/territories/life", json={"statement": "   "})
    assert r.status_code == 422


def test_unknown_field_rejected(client):
    r = client.put(f"{BASE}/territories/life", json={"statement": "ok", "founder_id": 999})
    assert r.status_code == 422


def test_re_upsert_replaces(client):
    client.put(f"{BASE}/territories/life", json={"statement": "first"})
    client.put(f"{BASE}/territories/life", json={"statement": "second"})
    body = client.get(BASE).json()
    assert body["territories"]["life"]["statement"] == "second"


# --- PUT /vision/summary -------------------------------------------------


def test_upsert_summary_200(client):
    r = client.put(f"{BASE}/summary", json={"target": "₹100Cr", "current": "₹3.4Cr", "unit": "ARR"})
    assert r.status_code == 200
    body = r.json()
    assert body == {"target": "₹100Cr", "current": "₹3.4Cr", "unit": "ARR", "updated_at": body["updated_at"]}


def test_upsert_summary_partial_keeps_other_fields(client):
    client.put(f"{BASE}/summary", json={"target": "₹100Cr", "current": "₹3.4Cr", "unit": "ARR"})
    r = client.put(f"{BASE}/summary", json={"current": "₹5Cr"})
    body = r.json()
    assert body["target"] == "₹100Cr" and body["unit"] == "ARR" and body["current"] == "₹5Cr"


def test_upsert_summary_empty_body_200(client):
    """All fields optional -- an empty PUT is a legal no-op update."""
    r = client.put(f"{BASE}/summary", json={})
    assert r.status_code == 200


def test_upsert_summary_overlong_field_422(client):
    r = client.put(f"{BASE}/summary", json={"target": "x" * 101})
    assert r.status_code == 422


# --- isolation ------------------------------------------------------------


def test_founder_isolation(client):
    client.put(f"{BASE}/territories/life", json={"statement": "founder 1's vision"})
    client.put(f"{BASE}/summary", json={"target": "founder 1's target"})
    client.founder["id"] = 2
    body = client.get(BASE).json()
    assert body["territories"]["life"]["statement"] == ""
    assert body["summary"]["target"] == ""
