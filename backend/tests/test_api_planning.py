"""API tests for the Planning endpoints. dependency_overrides inject an in-memory
service + a fake founder + canned diagnosis steps; no DB/auth backend."""

from datetime import datetime, timezone
from itertools import count
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.v1.planning.dependencies import (
    get_current_founder_id,
    get_diagnosis_steps,
    get_planning_service,
    require_plan_your_day,
)
from app.planning import build_planning_service

BASE = "/api/v1/planning"
T0 = datetime(2026, 7, 29, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def client():
    service = build_planning_service(clock=lambda c=count(1): T0, id_factory=(lambda c=count(1): f"id-{next(c)}"))
    founder = {"id": 1}
    app.dependency_overrides[get_current_founder_id] = lambda: founder["id"]
    app.dependency_overrides[get_planning_service] = lambda: service
    app.dependency_overrides[get_diagnosis_steps] = lambda: ["Interview churned users", "Book a call"]
    # These tests cover transport + service behaviour, not the paywall; the gate
    # itself is exercised against the real dependency in TestPlanGate below.
    app.dependency_overrides[require_plan_your_day] = lambda: None
    yield SimpleNamespace(http=TestClient(app), founder=founder, service=service)
    for dep in (get_current_founder_id, get_planning_service, get_diagnosis_steps,
                require_plan_your_day):
        app.dependency_overrides.pop(dep, None)


def _plan(client, title="Plan"):
    return client.http.post(f"{BASE}/plans", json={"title": title}).json()["plan_id"]


def _goal(client, plan_id, title="Goal"):
    return client.http.post(f"{BASE}/plans/{plan_id}/goals", json={"title": title}).json()["goal_id"]


# --- plans ------------------------------------------------------------------


def test_create_and_list_plans(client):
    created = client.http.post(f"{BASE}/plans", json={"title": "Q3 Growth"})
    assert created.status_code == 201 and created.json()["status"] == "active"
    assert client.http.get(f"{BASE}/plans").json()["total"] == 1


def test_plan_detail_nested(client):
    pid = _plan(client)
    gid = _goal(client, pid)
    client.http.post(f"{BASE}/goals/{gid}/tasks", json={"title": "Task 1"})
    detail = client.http.get(f"{BASE}/plans/{pid}").json()
    assert detail["plan"]["plan_id"] == pid
    assert len(detail["goals"]) == 1 and len(detail["goals"][0]["tasks"]) == 1


def test_update_archive_restore_plan(client):
    pid = _plan(client)
    assert client.http.patch(f"{BASE}/plans/{pid}", json={"title": "Renamed"}).json()["title"] == "Renamed"
    assert client.http.delete(f"{BASE}/plans/{pid}").json()["status"] == "archived"
    assert client.http.post(f"{BASE}/plans/{pid}/restore").json()["status"] == "active"


def test_create_plan_validation_422(client):
    assert client.http.post(f"{BASE}/plans", json={"title": ""}).status_code == 422


def test_unknown_plan_404(client):
    assert client.http.get(f"{BASE}/plans/nope").status_code == 404


# --- goals + tasks ----------------------------------------------------------


def test_goal_and_task_flow(client):
    pid = _plan(client)
    g = client.http.post(f"{BASE}/plans/{pid}/goals", json={"title": "Improve activation", "priority": "high"})
    assert g.status_code == 201 and g.json()["priority"] == "high"
    gid = g.json()["goal_id"]
    t = client.http.post(f"{BASE}/goals/{gid}/tasks", json={"title": "Interview users", "due_date": "2026-08-01"})
    assert t.status_code == 201 and t.json()["due_date"] == "2026-08-01"
    tid = t.json()["task_id"]
    done = client.http.patch(f"{BASE}/tasks/{tid}", json={"status": "done"})
    assert done.json()["status"] == "done" and done.json()["completed_at"] is not None
    assert client.http.get(f"{BASE}/goals/{gid}/tasks").json()["total"] == 1


def test_task_clear_due_date(client):
    pid = _plan(client)
    gid = _goal(client, pid)
    tid = client.http.post(f"{BASE}/goals/{gid}/tasks",
                           json={"title": "T", "due_date": "2026-08-01"}).json()["task_id"]
    assert client.http.patch(f"{BASE}/tasks/{tid}", json={"due_date": None}).json()["due_date"] is None


# --- diagnosis seeding ------------------------------------------------------


def test_seed_from_diagnosis(client):
    pid = _plan(client)
    r = client.http.post(f"{BASE}/plans/{pid}/seed-from-diagnosis")
    assert r.status_code == 201
    body = r.json()
    assert body["goal"]["source"] == "diagnosis"
    assert [t["title"] for t in body["tasks"]] == ["Interview churned users", "Book a call"]


# --- isolation --------------------------------------------------------------


def test_founder_isolation(client):
    pid = _plan(client, title="Founder 1 plan")
    client.founder["id"] = 2
    assert client.http.get(f"{BASE}/plans/{pid}").status_code == 404        # foreign plan hidden
    assert client.http.get(f"{BASE}/plans").json()["total"] == 0


# --- plan gating ------------------------------------------------------------
#
# These exercise the REAL require_plan_your_day dependency. Everything above
# overrides it; without this block the paywall would be entirely untested --
# which is exactly how it came to be missing in the first place.


class TestPlanGate:
    @staticmethod
    def _client(plan_type: str):
        from app.api.deps import get_founder_record
        from app.db.session import get_db

        app.dependency_overrides[get_founder_record] = lambda: SimpleNamespace(
            founder_id=1, plan_type=plan_type,
        )
        # require_feature reads the in-memory catalog, never the session, so a
        # placeholder keeps these tests off the database.
        app.dependency_overrides[get_db] = lambda: None
        app.dependency_overrides[get_planning_service] = lambda: build_planning_service(
            clock=lambda: T0, id_factory=(lambda c=count(1): f"gate-{next(c)}"))
        return TestClient(app)

    @staticmethod
    def _teardown():
        from app.api.deps import get_founder_record
        from app.db.session import get_db

        for dep in (get_founder_record, get_db, get_planning_service):
            app.dependency_overrides.pop(dep, None)

    def test_free_plan_is_refused(self):
        try:
            r = self._client("free").get(f"{BASE}/plans")
            assert r.status_code == 403, r.text
        finally:
            self._teardown()

    def test_free_plan_cannot_write_either(self):
        """The read path 403ing is not enough -- writes are the paywall hole."""
        try:
            r = self._client("free").post(f"{BASE}/plans", json={"title": "Sneaky"})
            assert r.status_code == 403, r.text
        finally:
            self._teardown()

    @pytest.mark.parametrize("plan_type", ["starter", "pro"])
    def test_paid_plans_are_allowed(self, plan_type):
        try:
            r = self._client(plan_type).get(f"{BASE}/plans")
            assert r.status_code == 200, r.text
        finally:
            self._teardown()
