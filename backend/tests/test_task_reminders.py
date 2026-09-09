"""Task reminder emails: scheduling from a due date, and the delivery worker.

The feature this covers had a specific failure mode -- every piece existed
except the one that sends -- so these tests care most about the seams: that a
row is actually written when a task is saved, that the worker moves every row
it looks at off "scheduled", and that nothing sends twice.
"""

from datetime import date, datetime, time, timedelta, timezone
from itertools import count
from types import SimpleNamespace

import pytest

from app.planning import (
    ProgressStatus,
    ReminderChannel,
    ReminderSource,
    ReminderStatus,
    build_planning_service,
)
from app.services import task_reminders

T0 = datetime(2026, 7, 29, 12, 0, 0, tzinfo=timezone.utc)


class StepClock:
    def __init__(self, start=T0, step=timedelta(seconds=1)):
        self._now, self._step = start, step

    def __call__(self):
        v = self._now
        self._now += self._step
        return v


def _ids():
    c = count(1)
    return lambda: f"id-{next(c)}"


def svc():
    return build_planning_service(clock=StepClock(), id_factory=_ids())


def _task(s, **kw):
    p = s.create_plan(1, title="P")
    g = s.add_goal(1, p.plan_id, title="G")
    return s.add_task(1, g.goal_id, title="Call Rajesh about pricing", **kw)


# --- when to remind ---------------------------------------------------------

def test_reminder_time_is_offset_before_a_timed_task():
    when = task_reminders.reminder_time_for(date(2026, 8, 1), time(15, 0), "UTC")
    assert when == datetime(2026, 8, 1, 14, 30, tzinfo=timezone.utc)


def test_dateless_task_has_no_reminder_time():
    assert task_reminders.reminder_time_for(None, None, "UTC") is None
    assert task_reminders.reminder_time_for(None, time(9, 0), "UTC") is None


def test_date_only_task_uses_the_calendar_default_hour():
    """Not midnight. An offset counted back from midnight fires at 23:30 the
    night before -- the bug the calendar path already documents."""
    when = task_reminders.reminder_time_for(date(2026, 8, 1), None, "UTC")
    assert when == datetime(2026, 8, 1, 8, 30, tzinfo=timezone.utc)


def test_reminder_time_is_in_the_founders_zone_not_the_servers():
    when = task_reminders.reminder_time_for(date(2026, 8, 1), time(9, 0), "Asia/Kolkata")
    # 09:00 IST is 03:30 UTC; the reminder is 30 minutes before that.
    assert when == datetime(2026, 8, 1, 3, 0, tzinfo=timezone.utc)


def test_unknown_timezone_falls_back_to_utc_rather_than_failing():
    """A bad IANA name comes from the browser. The reminder landing at the
    wrong hour is recoverable; a 500 on adding a task is not."""
    assert task_reminders.reminder_time_for(date(2026, 8, 1), time(9, 0), "Mars/Olympus") \
        == datetime(2026, 8, 1, 8, 30, tzinfo=timezone.utc)


# --- scheduling from a task -------------------------------------------------

def test_saving_a_dated_task_schedules_one_email_reminder():
    s = svc()
    t = _task(s, due_date=date(2026, 8, 1), due_time=time(15, 0))
    r = s.sync_task_reminder(1, t, remind_at=task_reminders.reminder_time_for(
        t.due_date, t.due_time, "UTC"), channel=ReminderChannel.EMAIL)
    assert r is not None
    assert r.source == ReminderSource.AUTO
    assert r.channel == ReminderChannel.EMAIL
    assert r.status == ReminderStatus.SCHEDULED
    assert len(s.list_reminders(1)) == 1


def test_a_task_with_no_due_date_schedules_nothing():
    s = svc()
    t = _task(s)
    assert s.sync_task_reminder(1, t, remind_at=None) is None
    assert s.list_reminders(1) == ()


def test_resaving_an_unchanged_task_does_not_add_a_second_reminder():
    """The hook runs on every save. Two rows would mean two emails."""
    s = svc()
    t = _task(s, due_date=date(2026, 8, 1), due_time=time(15, 0))
    when = task_reminders.reminder_time_for(t.due_date, t.due_time, "UTC")
    first = s.sync_task_reminder(1, t, remind_at=when, channel=ReminderChannel.EMAIL)
    again = s.sync_task_reminder(1, t, remind_at=when, channel=ReminderChannel.EMAIL)
    assert first.reminder_id == again.reminder_id
    scheduled = [r for r in s.list_reminders(1) if r.status == ReminderStatus.SCHEDULED]
    assert len(scheduled) == 1


def test_moving_the_due_date_moves_the_reminder_and_cancels_the_old_one():
    s = svc()
    t = _task(s, due_date=date(2026, 8, 1), due_time=time(15, 0))
    old = s.sync_task_reminder(1, t, remind_at=datetime(2026, 8, 1, 14, 30, tzinfo=timezone.utc),
                               channel=ReminderChannel.EMAIL)
    new = s.sync_task_reminder(1, t, remind_at=datetime(2026, 8, 3, 14, 30, tzinfo=timezone.utc),
                               channel=ReminderChannel.EMAIL)
    assert new.reminder_id != old.reminder_id
    by_id = {r.reminder_id: r for r in s.list_reminders(1)}
    assert by_id[old.reminder_id].status == ReminderStatus.CANCELLED
    assert by_id[new.reminder_id].status == ReminderStatus.SCHEDULED


def test_clearing_the_due_date_cancels_the_reminder():
    s = svc()
    t = _task(s, due_date=date(2026, 8, 1))
    r = s.sync_task_reminder(1, t, remind_at=datetime(2026, 8, 1, 8, 30, tzinfo=timezone.utc),
                             channel=ReminderChannel.EMAIL)
    assert s.sync_task_reminder(1, t, remind_at=None) is None
    assert s.list_reminders(1)[0].reminder_id == r.reminder_id
    assert s.list_reminders(1)[0].status == ReminderStatus.CANCELLED


def test_completing_a_task_cancels_its_reminder():
    """Being nagged about something already finished is how a founder learns
    to ignore the nagging."""
    s = svc()
    t = _task(s, due_date=date(2026, 8, 1), due_time=time(15, 0))
    when = datetime(2026, 8, 1, 14, 30, tzinfo=timezone.utc)
    s.sync_task_reminder(1, t, remind_at=when, channel=ReminderChannel.EMAIL)
    done = s.update_task(1, t.task_id, status=ProgressStatus.DONE)
    assert s.sync_task_reminder(1, done, remind_at=when) is None
    assert all(r.status == ReminderStatus.CANCELLED for r in s.list_reminders(1))


def test_a_reminder_in_the_past_is_not_scheduled():
    """Adding a task that was already due should not fire an email instantly."""
    s = svc()
    t = _task(s, due_date=date(2020, 1, 1))
    assert s.sync_task_reminder(
        1, t, remind_at=datetime(2020, 1, 1, tzinfo=timezone.utc)) is None
    assert s.list_reminders(1) == ()


def test_sync_never_touches_a_manual_reminder():
    """A founder's own reminder must survive editing the task's due date."""
    s = svc()
    t = _task(s, due_date=date(2026, 8, 1))
    mine = s.schedule_reminder(1, t.task_id,
                               remind_at=datetime(2026, 8, 1, 6, 0, tzinfo=timezone.utc),
                               note="my own")
    s.sync_task_reminder(1, t, remind_at=datetime(2026, 8, 1, 8, 30, tzinfo=timezone.utc),
                         channel=ReminderChannel.EMAIL)
    s.sync_task_reminder(1, t, remind_at=None)          # clear the date entirely
    survived = {r.reminder_id: r for r in s.list_reminders(1)}[mine.reminder_id]
    assert survived.status == ReminderStatus.SCHEDULED
    assert survived.source == ReminderSource.MANUAL


def test_sync_for_task_swallows_failures_so_a_save_cannot_be_lost():
    class Boom:
        def sync_task_reminder(self, *a, **kw):
            raise RuntimeError("repository down")
    task = SimpleNamespace(founder_id=1, task_id="t-1", due_date=date(2026, 8, 1),
                           due_time=None, status=ProgressStatus.TODO)
    assert task_reminders.sync_for_task(Boom(), task) is None


# --- the worker -------------------------------------------------------------

class FakeEntitlements:
    def __init__(self, allowed=True):
        self.allowed = allowed

    def has_feature(self, tier, feature):
        return self.allowed


class FakeDB:
    """Just enough Session for the worker: Founder lookup + a no-op commit."""

    def __init__(self, founder):
        self.founder = founder
        self.commits = 0

    def get(self, model, pk):
        return self.founder if self.founder and self.founder.founder_id == pk else None

    def commit(self):
        self.commits += 1


def _founder(**kw):
    return SimpleNamespace(
        founder_id=1, email="founder@example.com", full_name="Ayush",
        plan_type="pro", timezone="Asia/Kolkata",
        notification_preferences=kw.pop("prefs", {}), **kw)


@pytest.fixture
def worker(monkeypatch):
    """Runs send_due_reminders against an in-memory planning service, capturing
    every email instead of sending one."""
    sent = []
    monkeypatch.setattr(task_reminders, "send_task_reminder",
                        lambda *a, **kw: sent.append(a) or True)

    def run(service, founder, *, allowed=True, now=None):
        from app.core import container as container_mod
        monkeypatch.setattr(container_mod.container, "planning_service",
                            lambda db: service, raising=False)
        monkeypatch.setattr(container_mod.container, "entitlement_service",
                            lambda db: FakeEntitlements(allowed), raising=False)
        return task_reminders.send_due_reminders(
            FakeDB(founder), now=now or datetime(2026, 8, 1, 15, 0, tzinfo=timezone.utc))

    return SimpleNamespace(run=run, sent=sent)


def _due_reminder(s, *, remind_at=datetime(2026, 8, 1, 14, 30, tzinfo=timezone.utc)):
    t = _task(s, due_date=date(2026, 8, 1), due_time=time(15, 0))
    s.sync_task_reminder(1, t, remind_at=remind_at, channel=ReminderChannel.EMAIL)
    return t


def test_worker_sends_a_due_reminder_and_marks_it_sent(worker):
    s = svc()
    _due_reminder(s)
    counts = worker.run(s, _founder())
    assert counts["sent"] == 1
    assert len(worker.sent) == 1
    assert s.list_reminders(1)[0].status == ReminderStatus.SENT


def test_worker_does_not_send_the_same_reminder_twice(worker):
    s = svc()
    _due_reminder(s)
    worker.run(s, _founder())
    counts = worker.run(s, _founder())
    assert counts["sent"] == 0
    assert len(worker.sent) == 1


def test_worker_leaves_a_reminder_whose_time_has_not_come(worker):
    s = svc()
    _due_reminder(s, remind_at=datetime(2026, 8, 9, 14, 30, tzinfo=timezone.utc))
    counts = worker.run(s, _founder())
    assert counts["sent"] == 0
    assert s.list_reminders(1)[0].status == ReminderStatus.SCHEDULED


def test_worker_skips_a_founder_without_the_paid_feature(worker):
    s = svc()
    _due_reminder(s)
    counts = worker.run(s, _founder(), allowed=False)
    assert counts["skipped_plan"] == 1 and worker.sent == []
    # Still closed out: a row left scheduled is re-examined forever.
    assert s.list_reminders(1)[0].status == ReminderStatus.SENT


def test_worker_respects_the_opt_out(worker):
    s = svc()
    _due_reminder(s)
    counts = worker.run(s, _founder(prefs={"email_task_reminders": False}))
    assert counts["skipped_pref"] == 1 and worker.sent == []


def test_opting_out_of_call_reminders_does_not_silence_task_reminders(worker):
    """`email_reminders` gates the discovery-call reminder, not this one."""
    s = svc()
    _due_reminder(s)
    counts = worker.run(s, _founder(prefs={"email_reminders": False}))
    assert counts["sent"] == 1


def test_worker_drops_a_stale_reminder_without_emailing(worker):
    """After an outage, twenty emails about yesterday is worse than none."""
    s = svc()
    _due_reminder(s, remind_at=datetime(2026, 7, 30, 9, 0, tzinfo=timezone.utc))
    counts = worker.run(s, _founder())
    assert counts["stale"] == 1 and worker.sent == []
    assert s.list_reminders(1)[0].status == ReminderStatus.SENT


def test_worker_closes_out_a_reminder_whose_task_is_gone(worker):
    s = svc()
    t = _due_reminder(s)
    s.delete_task(1, t.task_id)
    counts = worker.run(s, _founder())
    assert counts["orphaned"] == 1 and worker.sent == []


def test_worker_does_not_email_about_a_completed_task(worker):
    s = svc()
    t = _due_reminder(s)
    s.update_task(1, t.task_id, status=ProgressStatus.DONE)
    counts = worker.run(s, _founder())
    assert counts["orphaned"] == 1 and worker.sent == []


def test_worker_ignores_in_app_reminders(worker):
    """The bell builds its own feed; those rows are not this worker's to send."""
    s = svc()
    t = _task(s, due_date=date(2026, 8, 1))
    s.schedule_reminder(1, t.task_id, remind_at=datetime(2026, 8, 1, 8, 0, tzinfo=timezone.utc),
                        channel=ReminderChannel.IN_APP)
    counts = worker.run(s, _founder())
    assert counts["sent"] == 0 and worker.sent == []
    assert s.list_reminders(1)[0].status == ReminderStatus.SCHEDULED


def test_one_bad_row_does_not_stop_the_others(worker, monkeypatch):
    s = svc()
    _due_reminder(s)
    _due_reminder(s)
    calls = count()
    real = s.mark_reminder_sent

    def flaky(reminder_id):
        if next(calls) == 0:
            raise RuntimeError("row is wrong somehow")
        return real(reminder_id)

    monkeypatch.setattr(s, "mark_reminder_sent", flaky)
    counts = worker.run(s, _founder())
    assert counts["failed"] == 1
    assert counts["sent"] == 2          # both attempted; one could not be marked
