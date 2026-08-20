"""API tests for the Achievements endpoints. dependency_overrides inject an
in-memory service + a fake founder; no DB/auth backend."""

from datetime import datetime, timedelta, timezone
from itertools import count
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.achievements import InMemoryAchievementRepository, build_achievement_service
from app.api.v1.achievements.dependencies import get_achievement_service, get_current_founder_id
from app.main import app

BASE = "/api/v1/achievements"
T0 = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)


class StepClock:
    def __init__(self, start=T0, step=timedelta(seconds=1)):
        self._now, self._step = start, step

    def __call__(self):
        v = self._now
        self._now += self._step
        return v


def _make_client(message_count=20):
    c = count(1)
    repo = InMemoryAchievementRepository({1: message_count})
    service = build_achievement_service(repo, clock=StepClock(), id_factory=lambda: f"a-{next(c)}")
    founder = {"id": 1}
    app.dependency_overrides[get_current_founder_id] = lambda: founder["id"]
    app.dependency_overrides[get_achievement_service] = lambda: service
    return SimpleNamespace(http=TestClient(app), founder=founder, service=service, repo=repo)


@pytest.fixture
def client():
    """Unlocked by default (20 messages >= threshold 15) -- most tests care
    about the CRUD surface, not the gate itself."""
    c = _make_client(message_count=20)
    yield c
    for dep in (get_current_founder_id, get_achievement_service):
        app.dependency_overrides.pop(dep, None)


@pytest.fixture
def locked_client():
    c = _make_client(message_count=5)
    yield c
    for dep in (get_current_founder_id, get_achievement_service):
        app.dependency_overrides.pop(dep, None)


# --- GET /achievements/engagement -------------------------------------------


def test_engagement_reports_real_count_and_unlocked(client):
    body = client.http.get(f"{BASE}/engagement").json()
    assert body == {"message_count": 20, "threshold": 15, "unlocked": True}


def test_engagement_reports_locked(locked_client):
    body = locked_client.http.get(f"{BASE}/engagement").json()
    assert body == {"message_count": 5, "threshold": 15, "unlocked": False}


# --- POST /achievements ------------------------------------------------


def test_create_achievement_201(client):
    r = client.http.post(BASE, json={
        "title": "Crossed ₹1Cr ARR", "description": "First repeatable engine.",
        "category": "Business", "occurred_on": "2022",
    })
    assert r.status_code == 201
    body = r.json()
    assert body["title"] == "Crossed ₹1Cr ARR"
    assert body["category"] == "Business" and body["occurred_on"] == "2022"
    assert body["founder_id"] == 1


def test_create_blocked_when_locked_403(locked_client):
    r = locked_client.http.post(BASE, json={"title": "Crossed ₹1Cr ARR"})
    assert r.status_code == 403


def test_missing_title_422(client):
    assert client.http.post(BASE, json={"description": "no title"}).status_code == 422


def test_empty_title_422(client):
    assert client.http.post(BASE, json={"title": "   "}).status_code == 422


def test_unknown_field_rejected(client):
    r = client.http.post(BASE, json={"title": "ok", "founder_id": 999})
    assert r.status_code == 422


# --- GET /achievements ---------------------------------------------------


def test_list_empty_for_new_founder(client):
    assert client.http.get(BASE).json() == {"achievements": [], "total": 0}


def test_list_newest_first(client):
    client.http.post(BASE, json={"title": "first"})
    client.http.post(BASE, json={"title": "second"})
    body = client.http.get(BASE).json()
    assert body["total"] == 2
    assert [a["title"] for a in body["achievements"]] == ["second", "first"]


# --- PATCH /achievements/{id} ------------------------------------------


def test_update_achievement(client):
    created = client.http.post(BASE, json={"title": "Original", "description": "v1"}).json()
    r = client.http.patch(f"{BASE}/{created['achievement_id']}", json={"description": "v2"})
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "Original" and body["description"] == "v2"


def test_update_nonexistent_404(client):
    assert client.http.patch(f"{BASE}/does-not-exist", json={"title": "x"}).status_code == 404


def test_update_someone_elses_achievement_404(client):
    created = client.http.post(BASE, json={"title": "mine"}).json()
    client.founder["id"] = 2
    r = client.http.patch(f"{BASE}/{created['achievement_id']}", json={"title": "hijacked"})
    assert r.status_code == 404


def test_update_still_works_once_locked(locked_client):
    """Update isn't gated -- only creating a NEW achievement is."""
    # Bootstrap: temporarily unlock to create one, then re-lock and edit it.
    locked_client.repo.set_message_count(1, 20)
    created = locked_client.http.post(BASE, json={"title": "mine"}).json()
    locked_client.repo.set_message_count(1, 0)
    r = locked_client.http.patch(f"{BASE}/{created['achievement_id']}", json={"title": "still editable"})
    assert r.status_code == 200


# --- DELETE /achievements/{id} -------------------------------------------


def test_delete_achievement_204(client):
    created = client.http.post(BASE, json={"title": "to delete"}).json()
    r = client.http.delete(f"{BASE}/{created['achievement_id']}")
    assert r.status_code == 204
    assert client.http.get(BASE).json()["total"] == 0


def test_delete_nonexistent_404(client):
    assert client.http.delete(f"{BASE}/does-not-exist").status_code == 404


def test_delete_someone_elses_achievement_404_and_survives(client):
    created = client.http.post(BASE, json={"title": "mine"}).json()
    client.founder["id"] = 2
    assert client.http.delete(f"{BASE}/{created['achievement_id']}").status_code == 404
    client.founder["id"] = 1
    assert client.http.get(BASE).json()["total"] == 1


# --- isolation ------------------------------------------------------------


def test_founder_isolation_on_list(client):
    client.http.post(BASE, json={"title": "founder 1's win"})
    client.founder["id"] = 2
    assert client.http.get(BASE).json() == {"achievements": [], "total": 0}
