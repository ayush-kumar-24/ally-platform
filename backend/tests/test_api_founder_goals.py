"""API tests for the Founder Goals endpoints. dependency_overrides inject an
in-memory service + a fake founder; no DB/auth backend."""

from datetime import datetime, timedelta, timezone
from itertools import count
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.v1.entitlement_gates import require_goals
from app.api.v1.founder_goals.dependencies import get_current_founder_id, get_founder_goal_service
from app.founder_goals import build_founder_goal_service
from app.main import app

BASE = "/api/v1/goals"
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
    c = count(1)
    service = build_founder_goal_service(clock=StepClock(), id_factory=lambda: f"g-{next(c)}")
    founder = {"id": 1}
    app.dependency_overrides[get_current_founder_id] = lambda: founder["id"]
    app.dependency_overrides[get_founder_goal_service] = lambda: service
    # Goals is gated on Feature.GOALS at the router. Overridden here so these
    # tests stay about goal behaviour and off the database; the gate itself is
    # exercised for real in TestPlanGate at the bottom of this file.
    app.dependency_overrides[require_goals] = lambda: None
    yield SimpleNamespace(http=TestClient(app), founder=founder, service=service)
    for dep in (get_current_founder_id, get_founder_goal_service, require_goals):
        app.dependency_overrides.pop(dep, None)


# --- POST /goals --------------------------------------------------------


def test_create_goal_201(client):
    r = client.http.post(BASE, json={"title": "₹5Cr annual revenue", "subtitle": "₹3.4Cr achieved"})
    assert r.status_code == 201
    body = r.json()
    assert body["title"] == "₹5Cr annual revenue"
    assert body["subtitle"] == "₹3.4Cr achieved"
    assert body["founder_id"] == 1
    assert body["created_at"].startswith("2026-08-20T12:00:00")


def test_subtitle_defaults_to_empty(client):
    assert client.http.post(BASE, json={"title": "Four focused days a week"}).json()["subtitle"] == ""


def test_missing_title_422(client):
    assert client.http.post(BASE, json={"subtitle": "no title"}).status_code == 422


def test_empty_title_422(client):
    assert client.http.post(BASE, json={"title": "   "}).status_code == 422


def test_unknown_field_rejected(client):
    """extra='forbid' -- a client can't inject e.g. founder_id or created_at."""
    r = client.http.post(BASE, json={"title": "ok", "founder_id": 999})
    assert r.status_code == 422


# --- GET /goals -----------------------------------------------------------


def test_list_empty_for_new_founder(client):
    body = client.http.get(BASE).json()
    assert body == {"goals": [], "total": 0}


def test_list_newest_first(client):
    client.http.post(BASE, json={"title": "first"})
    client.http.post(BASE, json={"title": "second"})
    body = client.http.get(BASE).json()
    assert body["total"] == 2
    assert [g["title"] for g in body["goals"]] == ["second", "first"]


# --- PATCH /goals/{id} ------------------------------------------------------


def test_update_goal(client):
    created = client.http.post(BASE, json={"title": "Original", "subtitle": "v1"}).json()
    r = client.http.patch(f"{BASE}/{created['goal_id']}", json={"subtitle": "v2"})
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "Original" and body["subtitle"] == "v2"


def test_update_nonexistent_goal_404(client):
    assert client.http.patch(f"{BASE}/does-not-exist", json={"title": "x"}).status_code == 404


def test_update_someone_elses_goal_404(client):
    created = client.http.post(BASE, json={"title": "mine"}).json()
    client.founder["id"] = 2
    r = client.http.patch(f"{BASE}/{created['goal_id']}", json={"title": "hijacked"})
    assert r.status_code == 404


# --- DELETE /goals/{id} -----------------------------------------------------


def test_delete_goal_204(client):
    created = client.http.post(BASE, json={"title": "to delete"}).json()
    r = client.http.delete(f"{BASE}/{created['goal_id']}")
    assert r.status_code == 204
    assert client.http.get(BASE).json()["total"] == 0


def test_delete_nonexistent_goal_404(client):
    assert client.http.delete(f"{BASE}/does-not-exist").status_code == 404


def test_delete_someone_elses_goal_404_and_survives(client):
    created = client.http.post(BASE, json={"title": "mine"}).json()
    client.founder["id"] = 2
    assert client.http.delete(f"{BASE}/{created['goal_id']}").status_code == 404
    client.founder["id"] = 1
    assert client.http.get(BASE).json()["total"] == 1


# --- isolation --------------------------------------------------------------


def test_founder_isolation_on_list(client):
    client.http.post(BASE, json={"title": "founder 1's goal"})
    client.founder["id"] = 2
    assert client.http.get(BASE).json() == {"goals": [], "total": 0}


# --- plan gating ------------------------------------------------------------
#
# These exercise the REAL require_goals dependency. Everything above overrides
# it; without this block the paywall would be entirely untested -- which is
# exactly how Goals came to be ungated in the first place. Same shape as
# TestPlanGate in test_api_planning.py, deliberately.


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
        app.dependency_overrides[get_current_founder_id] = lambda: 1
        app.dependency_overrides[get_founder_goal_service] = lambda: build_founder_goal_service(
            clock=StepClock(), id_factory=(lambda c=count(1): f"gate-{next(c)}"))
        return TestClient(app)

    @staticmethod
    def _teardown():
        from app.api.deps import get_founder_record
        from app.db.session import get_db

        for dep in (get_founder_record, get_db, get_current_founder_id,
                    get_founder_goal_service):
            app.dependency_overrides.pop(dep, None)

    @pytest.mark.parametrize("plan_type", ["starter", "pro"])
    def test_every_tier_that_includes_goals_reaches_the_endpoint(self, plan_type):
        try:
            r = self._client(plan_type).get(BASE)
            assert r.status_code == 200, r.text
        finally:
            self._teardown()

    @pytest.mark.parametrize("method,payload", [
        ("get", None),
        ("post", {"title": "Sneaky"}),
    ])
    def test_a_founder_with_no_features_is_refused(self, method, payload, monkeypatch):
        """The public-launch state. Proves the gate enforces on WRITES too --
        an ungated POST would let an off-plan founder create goals they cannot
        read back, which is worse than refusing them.

        The catalog is emptied rather than relying on what Free grants today,
        so this keeps testing the gate after launch flips that default.
        """
        from app.plans.catalog import PLANS, PlanTier

        free = PLANS[PlanTier.FREE]
        monkeypatch.setitem(PLANS, PlanTier.FREE,
                            free.__class__(**{**free.__dict__, "features": frozenset()}))
        try:
            http = self._client("free")
            r = http.request(method.upper(), BASE, json=payload)
            assert r.status_code == 403, r.text
            assert "goals" in r.text.lower()
        finally:
            self._teardown()
