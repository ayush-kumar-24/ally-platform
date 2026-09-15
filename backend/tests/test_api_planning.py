"""API tests for the Planning endpoints. dependency_overrides inject an in-memory
service + a fake founder + canned diagnosis steps; no DB/auth backend."""

from datetime import datetime, timezone
from dataclasses import replace
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


# --- reminder lead ----------------------------------------------------------


def test_task_reminder_lead_defaults_to_null(client):
    """Null, not 30. The row says "this founder never chose", which is what
    lets the platform default move later without dragging along every task
    whose owner simply never opened the picker."""
    gid = _goal(client, _plan(client))
    body = client.http.post(f"{BASE}/goals/{gid}/tasks", json={"title": "T"}).json()
    assert body["reminder_minutes_before"] is None


def test_task_reminder_lead_round_trips(client):
    gid = _goal(client, _plan(client))
    tid = client.http.post(f"{BASE}/goals/{gid}/tasks",
                           json={"title": "T", "due_date": "2026-08-01",
                                 "reminder_minutes_before": 15}).json()["task_id"]
    assert client.http.get(f"{BASE}/goals/{gid}/tasks").json()["tasks"][0][
        "reminder_minutes_before"] == 15
    patched = client.http.patch(f"{BASE}/tasks/{tid}",
                                json={"reminder_minutes_before": 1440}).json()
    assert patched["reminder_minutes_before"] == 1440


def test_task_reminder_lead_explicit_null_clears_it(client):
    """Same set/clear convention as the dates: omitted leaves it alone, null
    puts the task back on the platform default."""
    gid = _goal(client, _plan(client))
    tid = client.http.post(f"{BASE}/goals/{gid}/tasks",
                           json={"title": "T", "reminder_minutes_before": 15}).json()["task_id"]
    assert client.http.patch(f"{BASE}/tasks/{tid}", json={"title": "Renamed"}).json()[
        "reminder_minutes_before"] == 15
    assert client.http.patch(f"{BASE}/tasks/{tid}", json={"reminder_minutes_before": None}).json()[
        "reminder_minutes_before"] is None


def test_clearing_the_due_date_keeps_the_reminder_lead(client):
    """The lead is a preference about the task, not part of its schedule.
    Re-dating a task must not silently reset how far ahead it nudges."""
    gid = _goal(client, _plan(client))
    tid = client.http.post(f"{BASE}/goals/{gid}/tasks",
                           json={"title": "T", "due_date": "2026-08-01",
                                 "due_time": "15:00",
                                 "reminder_minutes_before": 15}).json()["task_id"]
    cleared = client.http.patch(f"{BASE}/tasks/{tid}", json={"due_date": None}).json()
    assert cleared["due_date"] is None and cleared["due_time"] is None
    assert cleared["reminder_minutes_before"] == 15


@pytest.mark.parametrize("bad", [-1, 10081])
def test_task_reminder_lead_out_of_range_is_422(client, bad):
    gid = _goal(client, _plan(client))
    r = client.http.post(f"{BASE}/goals/{gid}/tasks",
                         json={"title": "T", "reminder_minutes_before": bad})
    assert r.status_code == 422


def test_adding_a_dated_task_schedules_its_reminder(client):
    """End to end through the route: the founder picks 15 minutes, a reminder
    row exists at 15 minutes before, ready for the sweep to deliver."""
    gid = _goal(client, _plan(client))
    r = client.http.post(f"{BASE}/goals/{gid}/tasks",
                         json={"title": "Call Rajesh", "due_date": "2026-08-01",
                               "due_time": "15:00", "timezone": "UTC",
                               "reminder_minutes_before": 15})
    assert r.status_code == 201, r.text

    reminders = client.http.get(f"{BASE}/reminders").json()["reminders"]
    scheduled = [x for x in reminders if x["status"] == "scheduled"]
    assert len(scheduled) == 1
    assert scheduled[0]["remind_at"].startswith("2026-08-01T14:45")
    assert scheduled[0]["channel"] == "email"


def test_a_dateless_task_schedules_no_reminder(client):
    gid = _goal(client, _plan(client))
    client.http.post(f"{BASE}/goals/{gid}/tasks", json={"title": "Someday"})
    assert client.http.get(f"{BASE}/reminders").json()["reminders"] == []


def test_ticking_a_task_off_cancels_its_reminder(client):
    gid = _goal(client, _plan(client))
    tid = client.http.post(f"{BASE}/goals/{gid}/tasks",
                           json={"title": "T", "due_date": "2026-08-01",
                                 "due_time": "15:00", "timezone": "UTC"}).json()["task_id"]
    client.http.patch(f"{BASE}/tasks/{tid}", json={"status": "done"})
    statuses = [x["status"] for x in client.http.get(f"{BASE}/reminders").json()["reminders"]]
    assert statuses and all(st == "cancelled" for st in statuses)


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

    # The tiers that actually include Plan Your Day. "free" is not here because
    # at public launch Free is empty by design (settings.PUBLIC_LAUNCH), and
    # "basic" (the Rs 199 plan) is the diagnosis and report only -- it does not
    # carry the workspace, so its refusal is correct rather than a regression.
    @pytest.mark.parametrize("plan_type", ["starter", "pro"])
    def test_every_paid_tier_reaches_the_gate(self, plan_type):
        """Free included: Plan Your Day is temporarily in the Free feature set for
        the testing phase, so no tier is refused today."""
        try:
            r = self._client(plan_type).get(f"{BASE}/plans")
            assert r.status_code == 200, r.text
        finally:
            self._teardown()

    @pytest.mark.parametrize("method,payload", [
        ("get", None),
        ("post", {"title": "Sneaky"}),
    ])
    def test_a_tier_without_the_feature_is_refused(self, method, payload, monkeypatch):
        """Proves the gate actually enforces, independently of what the catalog
        happens to grant today.

        Asserting "free is refused" would have stopped testing anything the moment
        Plan Your Day moved into Free -- it would pass for the wrong reason, or
        fail and get deleted. So strip the feature from the plan the request
        resolves to and assert the refusal directly. Both verbs, because the read
        path 403ing is not the paywall -- writes are.
        """
        from app.plans import catalog

        stripped = {
            tier: replace(plan, features=plan.features - {catalog.Feature.PLAN_YOUR_DAY})
            for tier, plan in catalog.PLANS.items()
        }
        monkeypatch.setattr(catalog, "PLANS", stripped)
        try:
            client = self._client("free")
            r = getattr(client, method)(f"{BASE}/plans", **({"json": payload} if payload else {}))
            assert r.status_code == 403, r.text
            assert r.json()["error"] == "FeatureNotInPlanError"
        finally:
            self._teardown()


# --- the "this is scheduled" email, end to end through the endpoint ---------


class _StubDb:
    """Just enough Session for this route: one Founder lookup, plus the
    rollback the calendar hook calls when it cannot reach Google. The hook
    swallows its own failure and returns the task either way, which is what a
    founder with no calendar connected already gets."""

    def __init__(self, founder):
        self.founder = founder

    def get(self, model, pk):
        return self.founder

    def rollback(self):
        pass

    def commit(self):
        pass


@pytest.fixture
def mailed(client, monkeypatch):
    """The planning client, with the founder row and mail both stubbed.

    get_db is overridden rather than mocked deeper so the request goes through
    the real route, the real background queue and the real plan check --
    TestClient runs background tasks before returning, so an email queued by
    the handler has actually been sent by the time the response arrives.
    """
    from app.db.session import get_db
    from app.services import task_reminders
    from app.core import container as container_mod

    sent = []
    monkeypatch.setattr(task_reminders, "send_task_scheduled",
                        lambda *a, **kw: sent.append(a) or True)
    monkeypatch.setattr(container_mod.container, "entitlement_service",
                        lambda db: SimpleNamespace(has_feature=lambda tier, f: tier == "pro"),
                        raising=False)

    founder = SimpleNamespace(founder_id=1, email="founder@example.com",
                              full_name="Ayush", plan_type="pro",
                              notification_preferences={})
    app.dependency_overrides[get_db] = lambda: _StubDb(founder)
    yield SimpleNamespace(http=client.http, service=client.service,
                          founder=founder, sent=sent)
    app.dependency_overrides.pop(get_db, None)


def _goal_for_mail(client):
    plan = client.http.post(f"{BASE}/plans", json={"title": "P"}).json()["plan_id"]
    return client.http.post(f"{BASE}/plans/{plan}/goals", json={"title": "G"}).json()["goal_id"]


def test_scheduling_a_task_emails_a_pro_founder_immediately(mailed):
    """The whole point of the change: the email goes out on save, not thirty
    minutes before, so it does not depend on a sweep that runs when it likes."""
    goal = _goal_for_mail(mailed)
    r = mailed.http.post(f"{BASE}/goals/{goal}/tasks",
                         json={"title": "Call Rajesh", "due_date": "2026-08-01",
                               "due_time": "15:00", "timezone": "Asia/Kolkata"})
    assert r.status_code == 201, r.text
    assert len(mailed.sent) == 1
    to, _name, title, when, lead = mailed.sent[0]
    assert to == "founder@example.com"
    assert title == "Call Rajesh"
    assert "03:00 PM" in when
    # No reminder_minutes_before was sent, so the email states the platform
    # default rather than inventing one.
    assert lead == "30 minutes before"


def test_the_email_states_the_offset_the_founder_actually_chose(mailed):
    """The confirmation used to say "thirty minutes before" in hardcoded words.
    Now that the founder picks the offset, saying 30 to someone who chose 15
    would be the email confidently lying about when they will be nudged."""
    goal = _goal_for_mail(mailed)
    r = mailed.http.post(f"{BASE}/goals/{goal}/tasks",
                         json={"title": "Call Rajesh", "due_date": "2026-08-01",
                               "due_time": "15:00", "timezone": "Asia/Kolkata",
                               "reminder_minutes_before": 15})
    assert r.status_code == 201, r.text
    assert r.json()["reminder_minutes_before"] == 15
    assert mailed.sent[0][4] == "15 minutes before"


def test_choosing_zero_is_a_choice_and_not_a_missing_value(mailed):
    """0 must not collapse into the default the way a falsy check would."""
    goal = _goal_for_mail(mailed)
    r = mailed.http.post(f"{BASE}/goals/{goal}/tasks",
                         json={"title": "Standup", "due_date": "2026-08-01",
                               "due_time": "09:30", "timezone": "Asia/Kolkata",
                               "reminder_minutes_before": 0})
    assert r.status_code == 201, r.text
    assert r.json()["reminder_minutes_before"] == 0
    assert mailed.sent[0][4] == "when it is due"


def test_a_task_with_no_date_sends_nothing(mailed):
    goal = _goal_for_mail(mailed)
    r = mailed.http.post(f"{BASE}/goals/{goal}/tasks", json={"title": "Someday"})
    assert r.status_code == 201, r.text
    assert mailed.sent == []


def test_a_non_pro_founder_gets_no_email(mailed):
    mailed.founder.plan_type = "starter"
    goal = _goal_for_mail(mailed)
    r = mailed.http.post(f"{BASE}/goals/{goal}/tasks",
                         json={"title": "Call Rajesh", "due_date": "2026-08-01",
                               "due_time": "15:00", "timezone": "Asia/Kolkata"})
    assert r.status_code == 201, r.text
    assert mailed.sent == []


def test_rescheduling_emails_again_but_renaming_does_not(mailed):
    """A second email is worth sending when the moment moved, and is noise
    otherwise -- which is how a useful email becomes one people filter out."""
    goal = _goal_for_mail(mailed)
    task = mailed.http.post(f"{BASE}/goals/{goal}/tasks",
                            json={"title": "Call Rajesh", "due_date": "2026-08-01",
                                  "due_time": "15:00", "timezone": "Asia/Kolkata"}).json()
    assert len(mailed.sent) == 1

    mailed.http.patch(f"{BASE}/tasks/{task['task_id']}",
                      json={"title": "Call Rajesh about pricing", "timezone": "Asia/Kolkata"})
    assert len(mailed.sent) == 1, "a rename is not a reschedule"

    mailed.http.patch(f"{BASE}/tasks/{task['task_id']}",
                      json={"due_time": "16:30", "timezone": "Asia/Kolkata"})
    assert len(mailed.sent) == 2, "moving the time should confirm the new one"
    assert "04:30 PM" in mailed.sent[1][3]


def test_ticking_a_task_off_sends_nothing(mailed):
    goal = _goal_for_mail(mailed)
    task = mailed.http.post(f"{BASE}/goals/{goal}/tasks",
                            json={"title": "Call Rajesh", "due_date": "2026-08-01",
                                  "due_time": "15:00", "timezone": "Asia/Kolkata"}).json()
    mailed.sent.clear()
    mailed.http.patch(f"{BASE}/tasks/{task['task_id']}",
                      json={"status": "done", "timezone": "Asia/Kolkata"})
    assert mailed.sent == []
