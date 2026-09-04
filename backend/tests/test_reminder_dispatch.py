"""The worker that finally delivers the reminders founders schedule.

Before this existed, every reminder ever created sat at status='scheduled'
forever: the scheduling API, the due-reminder query, the sent-marking and the
email sender were all present, and nothing joined them. These tests pin the
three decisions the worker makes -- plan, preference, address -- and the queue
behaviour that keeps it from mailing the same reminder twice or growing without
bound.

`send_email` is patched throughout: what matters here is WHO we decided to mail,
not SMTP, which app/services/email.py already stubs out when unconfigured.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.planning.models import ReminderChannel, ReminderStatus
from app.planning.service import build_planning_service
from app.plans.catalog import PlanTier
from app.plans.service import build_entitlement_service
from app.services import reminder_dispatch

T0 = datetime(2026, 9, 4, 9, 0, tzinfo=timezone.utc)
LATER = T0 + timedelta(hours=2)


class FakeFounder:
    def __init__(self, tier=PlanTier.PRO, email="f@example.com", prefs=None):
        self.founder_id = 1
        self.plan_type = tier.value
        self.email = email
        self.notification_preferences = prefs


class FakeDB:
    """Just enough Session for the worker: founder lookup, and a record of the
    Notifications rows it wrote."""

    def __init__(self, founder):
        self._founder = founder
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    def get(self, _model, _pk):
        return self._founder

    def add(self, row):
        self.added.append(row)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


@pytest.fixture
def sent(monkeypatch):
    calls = []
    monkeypatch.setattr(reminder_dispatch, "send_email",
                        lambda to, subject, text, html=None: calls.append((to, subject)) or True)
    return calls


def _planning_with_reminder(channel=ReminderChannel.EMAIL, note=""):
    """A real PlanningService over the in-memory repo, carrying one due reminder."""
    svc = build_planning_service(clock=lambda: T0)
    plan = svc.create_plan(1, title="This week")
    goal = svc.add_goal(1, plan.plan_id, title="Ship pricing")
    task = svc.add_task(1, goal.goal_id, title="Publish the plans page")
    svc.schedule_reminder(1, task.task_id, remind_at=T0 + timedelta(hours=1),
                          channel=channel, note=note)
    return svc, task


def _run(founder, planning, now=LATER):
    db = FakeDB(founder)
    result = reminder_dispatch.send_due_task_reminders(
        db, now=now, planning_service=planning,
        entitlements=build_entitlement_service())
    return result, db


# --- the happy path ---------------------------------------------------------


def test_a_due_email_reminder_is_sent_to_a_pro_founder(sent):
    planning, task = _planning_with_reminder()
    result, db = _run(FakeFounder(), planning)

    assert result["sent"] == 1
    assert sent == [("f@example.com", f"Reminder: {task.title}")]
    assert planning.due_reminders(before=LATER) == ()   # left the queue
    assert db.added and db.added[0].channel == "email"


def test_the_email_names_the_task_and_carries_the_founders_note(sent, monkeypatch):
    bodies = []
    monkeypatch.setattr(reminder_dispatch, "send_email",
                        lambda to, subject, text, html=None: bodies.append((text, html)) or True)
    planning, task = _planning_with_reminder(note="before the standup")
    _run(FakeFounder(), planning)

    text, html = bodies[0]
    assert task.title in text and "before the standup" in text
    assert task.title in html and "before the standup" in html


# --- the three refusals -----------------------------------------------------


@pytest.mark.parametrize("tier", [PlanTier.BASIC, PlanTier.STARTER])
def test_a_founder_below_pro_is_not_emailed(sent, tier):
    """Email reminders are a Rs 999 promise. A reminder scheduled while on Pro
    must stop mailing after a downgrade, so the plan is checked at DELIVERY
    time, not when the reminder was created."""
    planning, _ = _planning_with_reminder()
    result, _ = _run(FakeFounder(tier=tier), planning)

    assert sent == []
    assert result["skipped_plan"] == 1 and result["sent"] == 0


def test_a_founder_who_turned_reminders_off_is_not_emailed(sent):
    """An entitlement says we MAY email; the preference says whether they WANT
    it, and the preference wins."""
    planning, _ = _planning_with_reminder()
    result, _ = _run(FakeFounder(prefs={"email_reminders": False}), planning)

    assert sent == [] and result["skipped_pref"] == 1


def test_reminders_stay_on_when_the_founder_has_never_touched_the_setting(sent):
    """Absent preferences must not read as "off" -- that would silently stop
    mailing every founder who never opened notification settings."""
    planning, _ = _planning_with_reminder()
    result, _ = _run(FakeFounder(prefs=None), planning)
    assert result["sent"] == 1

    planning2, _ = _planning_with_reminder()
    result2, _ = _run(FakeFounder(prefs={}), planning2)
    assert result2["sent"] == 1


def test_a_founder_with_no_address_is_not_emailed(sent):
    planning, _ = _planning_with_reminder()
    result, _ = _run(FakeFounder(email=""), planning)
    assert sent == [] and result["skipped_no_email"] == 1


# --- queue behaviour --------------------------------------------------------


def test_a_skipped_reminder_leaves_the_queue_instead_of_being_reconsidered(sent):
    """The alternative is a queue that grows forever and mails a founder the
    moment they upgrade -- reminders about tasks whose date has long passed."""
    planning, _ = _planning_with_reminder()
    _run(FakeFounder(tier=PlanTier.BASIC), planning)

    assert planning.due_reminders(before=LATER) == ()


def test_a_second_sweep_does_not_send_the_same_reminder_again(sent):
    planning, _ = _planning_with_reminder()
    _run(FakeFounder(), planning)
    result2, _ = _run(FakeFounder(), planning)

    assert len(sent) == 1
    assert result2["sent"] == 0


def test_a_reminder_that_is_not_due_yet_is_left_alone(sent):
    planning, _ = _planning_with_reminder()
    result, _ = _run(FakeFounder(), planning, now=T0 + timedelta(minutes=30))

    assert sent == [] and result["sent"] == 0
    assert len(planning.due_reminders(before=LATER)) == 1


def test_in_app_reminders_are_left_for_the_in_app_surface(sent):
    """Not a paid feature and not something this worker delivers -- marking them
    sent here would quietly consume a nudge the founder never received."""
    planning, _ = _planning_with_reminder(channel=ReminderChannel.IN_APP)
    result, _ = _run(FakeFounder(), planning)

    assert sent == [] and result["in_app"] == 1
    assert len(planning.due_reminders(before=LATER)) == 1


def test_a_reminder_is_marked_sent_even_when_delivery_reports_failure(monkeypatch):
    """send_email is best-effort by contract -- False in stub mode and on a
    delivery error. Keying the queue on its result would re-send the same
    reminder on every sweep for as long as mail stays misconfigured."""
    monkeypatch.setattr(reminder_dispatch, "send_email",
                        lambda to, subject, text, html=None: False)
    planning, _ = _planning_with_reminder()
    result, _ = _run(FakeFounder(), planning)

    assert result["sent"] == 1
    assert planning.due_reminders(before=LATER) == ()


def test_one_failing_reminder_does_not_strand_the_rest(monkeypatch):
    """A bad address or a closed SMTP connection must not take out every
    reminder queued behind it."""
    planning, _ = _planning_with_reminder()
    plan = planning.list_plans(1)[0]
    goal = planning.list_goals(1, plan.plan_id)[0]
    second = planning.add_task(1, goal.goal_id, title="Second task")
    planning.schedule_reminder(1, second.task_id, remind_at=T0 + timedelta(hours=1),
                               channel=ReminderChannel.EMAIL)

    calls = []

    def flaky(to, subject, text, html=None):
        calls.append(subject)
        if len(calls) == 1:
            raise RuntimeError("smtp exploded")
        return True

    monkeypatch.setattr(reminder_dispatch, "send_email", flaky)
    result, _ = _run(FakeFounder(), planning)

    assert result["failed"] == 1 and result["sent"] == 1
    assert len(calls) == 2


def test_the_delivery_is_recorded_against_the_founder(sent):
    """Filed in `notifications` so a founder asking "did you email me?" has an
    answer, and under a `type` the table's CHECK constraint actually permits."""
    planning, task = _planning_with_reminder()
    _, db = _run(FakeFounder(), planning)

    row = db.added[0]
    assert row.founder_id == 1
    assert row.type == "follow_up"
    assert row.channel == "email"
    assert task.title in row.title
    assert row.metadata_["task_id"] == task.task_id


# --- the endpoint a cron actually calls -------------------------------------


def _client():
    from fastapi.testclient import TestClient

    from app.db.session import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: FakeDB(FakeFounder())
    client = TestClient(app, raise_server_exceptions=False)
    return client, app


def test_the_reminder_sweep_refuses_an_unauthenticated_caller(monkeypatch):
    """It runs for no founder and takes no token -- a shared secret is the only
    thing standing between the open internet and everyone's inbox."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "INTERNAL_JOBS_SECRET", "s3cret", raising=False)
    client, app = _client()
    try:
        assert client.post("/api/v1/internal/jobs/send-reminders").status_code == 401
        assert client.post("/api/v1/internal/jobs/send-reminders",
                           headers={"X-Internal-Secret": "wrong"}).status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_one_broken_queue_does_not_take_out_the_other(monkeypatch):
    """Discovery-call reminders are transactional and have nothing to do with
    plans. A bug in the task sweep must not cancel someone's call reminder."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "INTERNAL_JOBS_SECRET", "s3cret", raising=False)
    monkeypatch.setattr(reminder_dispatch, "send_due_task_reminders",
                        lambda db, **kw: (_ for _ in ()).throw(RuntimeError("boom")))
    import app.services.discovery_notifications as dn
    monkeypatch.setattr(dn, "send_due_reminders", lambda db, **kw: {"24h": 1, "1h": 0})

    client, app = _client()
    try:
        r = client.post("/api/v1/internal/jobs/send-reminders",
                        headers={"X-Internal-Secret": "s3cret"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert "error" in body["tasks"]
        assert body["calls"] == {"24h": 1, "1h": 0}
    finally:
        app.dependency_overrides.clear()
