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
from app.core.config import settings
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


def test_the_lead_can_be_set_per_task():
    """Same rule as the calendar popup, from the same number: the founder's
    choice, not a platform constant."""
    when = task_reminders.reminder_time_for(date(2026, 8, 1), time(15, 0), "UTC", 15)
    assert when == datetime(2026, 8, 1, 14, 45, tzinfo=timezone.utc)
    at_the_time = task_reminders.reminder_time_for(date(2026, 8, 1), time(15, 0), "UTC", 0)
    assert at_the_time == datetime(2026, 8, 1, 15, 0, tzinfo=timezone.utc)


def test_lead_minutes_for_falls_back_only_when_nothing_was_chosen():
    """None is "never chose", 0 is a choice -- and they must not collapse."""
    assert (task_reminders.lead_minutes_for(SimpleNamespace(reminder_minutes_before=None))
            == settings.TASK_REMINDER_MINUTES_BEFORE)
    assert task_reminders.lead_minutes_for(SimpleNamespace(reminder_minutes_before=0)) == 0
    assert task_reminders.lead_minutes_for(SimpleNamespace(reminder_minutes_before=15)) == 15


@pytest.mark.parametrize("minutes,phrase", [
    (0, "when it is due"),
    (5, "5 minutes before"),
    (30, "30 minutes before"),
    (60, "1 hour before"),
    (120, "2 hours before"),
    (1440, "1 day before"),
])
def test_lead_phrase_reads_like_a_person_wrote_it(minutes, phrase):
    """"1440 minutes before" is true and reads like a machine."""
    assert task_reminders.lead_phrase(minutes) == phrase


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
    every email instead of sending one -- and every bell row instead of
    writing one, since the same reminder goes to the bell for a founder whose
    plan has no email."""
    sent = []
    monkeypatch.setattr(task_reminders, "send_task_reminder",
                        lambda *a, **kw: sent.append(a) or True)
    belled = []
    # Returns a stand-in ROW, because that is what the worker counts on: a
    # real notify() returns None when it wrote nothing, and the worker must
    # not report a delivery in that case.
    monkeypatch.setattr(task_reminders, "notify",
                        lambda db, **kw: belled.append(kw) or SimpleNamespace(notification_id=len(belled)))

    def run(service, founder, *, allowed=True, now=None):
        from app.core import container as container_mod
        monkeypatch.setattr(container_mod.container, "planning_service",
                            lambda db: service, raising=False)
        monkeypatch.setattr(container_mod.container, "entitlement_service",
                            lambda db: FakeEntitlements(allowed), raising=False)
        return task_reminders.send_due_reminders(
            FakeDB(founder), now=now or datetime(2026, 8, 1, 15, 0, tzinfo=timezone.utc))

    return SimpleNamespace(run=run, sent=sent, belled=belled)


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


def test_a_founder_without_the_paid_feature_is_reminded_in_the_bell(worker):
    """Every founder is reminded; only the channel is sold. Starter plans a
    day too, and used to get nothing at all at the reminder moment."""
    s = svc()
    _due_reminder(s)
    counts = worker.run(s, _founder(), allowed=False)

    assert counts["in_app"] == 1 and counts["sent"] == 0
    assert worker.sent == [], "no email for a plan that does not include it"
    assert len(worker.belled) == 1
    bell = worker.belled[0]
    assert bell["type"] == "task_reminder"
    assert bell["action_url"] == "/app/plan"
    assert "Call Rajesh about pricing" in bell["title"]
    assert "in 30 minutes" in bell["body"]
    # Still closed out: a row left scheduled is re-examined forever.
    assert s.list_reminders(1)[0].status == ReminderStatus.SENT


def test_turning_off_the_email_moves_the_reminder_to_the_bell(worker):
    """`email_task_reminders` off means no EMAIL, not no reminder -- the bell
    has its own switch for that (in_app_all, honoured inside notify)."""
    s = svc()
    _due_reminder(s)
    counts = worker.run(s, _founder(prefs={"email_task_reminders": False}))
    assert counts["in_app"] == 1 and worker.sent == []
    assert len(worker.belled) == 1


def test_a_pro_founder_gets_the_email_and_no_bell(worker):
    """The two channels are alternatives, not a pair -- a Pro founder being
    told twice about one task is how a useful reminder becomes noise."""
    s = svc()
    _due_reminder(s)
    counts = worker.run(s, _founder())
    assert counts["sent"] == 1 and counts["in_app"] == 0
    assert worker.belled == []


def test_a_bell_row_that_was_not_written_is_not_counted_as_delivered(worker, monkeypatch):
    """notify() returns None when the founder muted the bell, when the row is
    already there, and when the write failed. Counting those as `in_app` would
    report a healthy sweep while the founder was told nothing -- which is the
    precise failure this whole feature exists to end."""
    monkeypatch.setattr(task_reminders, "notify", lambda db, **kw: None)
    s = svc()
    _due_reminder(s)
    counts = worker.run(s, _founder(), allowed=False)
    assert counts["in_app"] == 0
    assert counts["skipped_pref"] == 1
    # Still closed out -- an unwritable row must not be retried forever.
    assert s.list_reminders(1)[0].status == ReminderStatus.SENT


def test_the_bell_reminder_is_keyed_per_reminder_so_rescheduling_re_notifies(worker):
    """Keyed on the row, not the task: moving a task cancels its reminder and
    writes a new one, and the founder needs telling about the new time."""
    s = svc()
    t = _due_reminder(s)
    worker.run(s, _founder(), allowed=False)
    first = worker.belled[0]["dedup_key"]
    assert first.startswith("task_reminder:")

    moved = s.update_task(1, t.task_id, due_date=date(2026, 8, 2))
    task_reminders.sync_for_task(s, moved, timezone_name="UTC")
    worker.run(s, _founder(), allowed=False,
               now=datetime(2026, 8, 2, 15, 0, tzinfo=timezone.utc))
    assert worker.belled[1]["dedup_key"] != first


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


def test_a_late_day_before_reminder_still_sends_because_it_beats_the_task(worker):
    """The old rule measured staleness from the ROW: a "1 day before" reminder
    delayed four hours was thrown away, even though it was still twenty hours
    ahead of the task and exactly as useful."""
    s = svc()
    t = _task(s, due_date=date(2026, 8, 1), due_time=time(15, 0),
              reminder_minutes_before=1440)
    task_reminders.sync_for_task(s, t, timezone_name="UTC")   # remind_at = Jul 31 15:00
    counts = worker.run(s, _founder(),
                        now=datetime(2026, 7, 31, 19, 0, tzinfo=timezone.utc))
    assert counts["sent"] == 1 and counts["stale"] == 0


def test_a_late_five_minute_reminder_is_dropped_because_the_task_has_passed(worker):
    """The mirror image: the old rule would have sent this half an hour AFTER
    the task was due, which is a nag about something already missed."""
    s = svc()
    t = _task(s, due_date=date(2026, 8, 1), due_time=time(15, 0),
              reminder_minutes_before=5)
    task_reminders.sync_for_task(s, t, timezone_name="UTC")   # remind_at = 14:55
    counts = worker.run(s, _founder(),
                        now=datetime(2026, 8, 1, 15, 30, tzinfo=timezone.utc))
    assert counts["stale"] == 1 and worker.sent == []


def test_an_at_the_time_reminder_survives_the_sweep_running_just_after(worker):
    """remind_at IS the task's moment for a 0 offset, so every sweep runs after
    it. Without the grace window this offset could never be delivered."""
    s = svc()
    t = _task(s, due_date=date(2026, 8, 1), due_time=time(15, 0),
              reminder_minutes_before=0)
    task_reminders.sync_for_task(s, t, timezone_name="UTC")
    counts = worker.run(s, _founder(),
                        now=datetime(2026, 8, 1, 15, 1, tzinfo=timezone.utc))
    assert counts["sent"] == 1


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


# --- the confirmation sent when a task is scheduled -------------------------
#
# Replaced the T-30 email on 2026-09-11. The thirty-minute warning is already
# delivered twice (Google Calendar popup, in-app bell), and the email version
# depended on a sweep GitHub ran every two to five hours instead of every ten
# minutes, so most of them were dropped as stale rather than sent.


@pytest.fixture
def confirm(monkeypatch):
    """notify_task_scheduled with the plan lookup stubbed and mail captured."""
    sent = []
    monkeypatch.setattr(task_reminders, "send_task_scheduled",
                        lambda *a: sent.append(a) or True)

    def run(founder, task, *, allowed=True, tz="Asia/Kolkata"):
        from app.core import container as container_mod
        monkeypatch.setattr(container_mod.container, "entitlement_service",
                            lambda db: FakeEntitlements(allowed), raising=False)
        return task_reminders.notify_task_scheduled(
            FakeDB(founder), founder, task, timezone_name=tz)

    return SimpleNamespace(run=run, sent=sent)


def test_scheduling_a_dated_task_emails_a_pro_founder(confirm):
    s = svc()
    t = _task(s, due_date=date(2026, 8, 1), due_time=time(15, 0))
    job = confirm.run(_founder(), t)
    assert job is not None, "a Pro founder with a dated task should be emailed"
    job()
    (to, name, title, when, lead), = confirm.sent
    assert to == "founder@example.com"
    assert title == "Call Rajesh about pricing"
    # 15:00 as the founder set it, in their zone -- not shifted into UTC.
    assert "03:00 PM" in when
    # No choice was made on this task, so the email states the platform default.
    assert lead == "30 minutes before"


def test_the_confirmation_states_the_offset_the_founder_chose(confirm):
    """The sentence used to be the hardcoded words "thirty minutes before".
    Telling a founder who picked an hour that they will be nudged in thirty
    minutes is the email lying about the one thing it is there to promise."""
    s = svc()
    t = _task(s, due_date=date(2026, 8, 1), due_time=time(15, 0),
              reminder_minutes_before=60)
    confirm.run(_founder(), t)()
    assert confirm.sent[0][4] == "1 hour before"


def test_nothing_is_sent_until_the_returned_job_is_run(confirm):
    """The send is handed back, never done inline: SMTP can take seconds and
    can hang, and neither belongs in the request that saved the task."""
    s = svc()
    t = _task(s, due_date=date(2026, 8, 1), due_time=time(15, 0))
    job = confirm.run(_founder(), t)
    assert confirm.sent == []
    job()
    assert len(confirm.sent) == 1


def test_a_task_with_no_due_date_is_not_confirmed(confirm):
    """No date, no moment to confirm -- a title-only to-do is a list item, not
    an appointment, and must not reach anyone's inbox."""
    s = svc()
    assert confirm.run(_founder(), _task(s)) is None
    assert confirm.sent == []


def test_a_founder_without_the_paid_feature_is_not_emailed(confirm):
    s = svc()
    t = _task(s, due_date=date(2026, 8, 1), due_time=time(15, 0))
    # _founder() fixes plan_type, so it is set after construction rather than
    # through kwargs it would collide with.
    founder = _founder()
    founder.plan_type = "starter"
    assert confirm.run(founder, t, allowed=False) is None
    assert confirm.sent == []


def test_the_opt_out_silences_the_confirmation(confirm):
    s = svc()
    t = _task(s, due_date=date(2026, 8, 1), due_time=time(15, 0))
    founder = _founder(prefs={"email_task_reminders": False})
    assert confirm.run(founder, t) is None


def test_opting_out_of_call_reminders_does_not_silence_task_emails(confirm):
    """email_reminders gates the reminder for a call the founder PAID for.
    Sharing it would mean silencing task mail also silences that."""
    s = svc()
    t = _task(s, due_date=date(2026, 8, 1), due_time=time(15, 0))
    founder = _founder(prefs={"email_reminders": False})
    assert confirm.run(founder, t) is not None


def test_a_founder_with_no_email_address_is_skipped(confirm):
    s = svc()
    t = _task(s, due_date=date(2026, 8, 1), due_time=time(15, 0))
    founder = _founder()
    founder.email = None
    assert confirm.run(founder, t) is None


def test_a_dateless_time_uses_the_same_default_hour_as_the_calendar(confirm):
    """A date with no time is 9am in both the calendar event and the email, so
    the two can never disagree about when the thing is."""
    s = svc()
    t = _task(s, due_date=date(2026, 8, 1))
    confirm.run(_founder(), t)()
    (_, _, _, when, _lead), = confirm.sent
    assert "09:00 AM" in when


def test_a_plan_lookup_failure_sends_nothing(confirm, monkeypatch):
    """Silence is the safe side of an unknown plan: better no email than one to
    a founder who has not paid for it."""
    s = svc()
    t = _task(s, due_date=date(2026, 8, 1), due_time=time(15, 0))
    from app.core import container as container_mod
    monkeypatch.setattr(container_mod.container, "entitlement_service",
                        lambda db: (_ for _ in ()).throw(RuntimeError("db down")),
                        raising=False)
    founder = _founder()
    assert task_reminders.notify_task_scheduled(
        FakeDB(founder), founder, t, timezone_name="UTC") is None
    assert confirm.sent == []


def test_a_send_that_fails_is_logged_not_raised(confirm, monkeypatch):
    """The job runs after the response has gone out. Raising there cannot reach
    the founder, so it must not take the worker down with it."""
    s = svc()
    t = _task(s, due_date=date(2026, 8, 1), due_time=time(15, 0))
    job = confirm.run(_founder(), t)
    monkeypatch.setattr(task_reminders, "send_task_scheduled",
                        lambda *a: (_ for _ in ()).throw(OSError("smtp down")))
    job()   # must not raise


def test_sync_for_task_schedules_at_the_founders_own_offset():
    """The whole point: the row lands at the offset picked in Plan Your Day,
    not at a platform constant."""
    s = svc()
    t = _task(s, due_date=date(2026, 8, 1), due_time=time(15, 0),
              reminder_minutes_before=15)
    r = task_reminders.sync_for_task(s, t, timezone_name="UTC")
    assert r is not None
    assert r.remind_at == datetime(2026, 8, 1, 14, 45, tzinfo=timezone.utc)
    assert r.channel == ReminderChannel.EMAIL
    assert r.status == ReminderStatus.SCHEDULED


def test_sync_for_task_falls_back_to_the_platform_default():
    """A task created before the picker existed still gets a reminder."""
    s = svc()
    t = _task(s, due_date=date(2026, 8, 1), due_time=time(15, 0))
    r = task_reminders.sync_for_task(s, t, timezone_name="UTC")
    assert r.remind_at == datetime(2026, 8, 1, 14, 30, tzinfo=timezone.utc)


def test_changing_the_offset_moves_the_reminder():
    """Editing the picker has to move the row, or the founder's change is a
    setting that displays correctly and does nothing."""
    s = svc()
    t = _task(s, due_date=date(2026, 8, 1), due_time=time(15, 0),
              reminder_minutes_before=30)
    first = task_reminders.sync_for_task(s, t, timezone_name="UTC")
    moved = s.update_task(1, t.task_id, reminder_minutes_before=5)
    second = task_reminders.sync_for_task(s, moved, timezone_name="UTC")

    assert second.remind_at == datetime(2026, 8, 1, 14, 55, tzinfo=timezone.utc)
    by_id = {r.reminder_id: r for r in s.list_reminders(1)}
    assert by_id[first.reminder_id].status == ReminderStatus.CANCELLED
    assert by_id[second.reminder_id].status == ReminderStatus.SCHEDULED
    scheduled = [r for r in s.list_reminders(1) if r.status == ReminderStatus.SCHEDULED]
    assert len(scheduled) == 1, "one task, one reminder"


def test_sync_for_task_schedules_nothing_for_a_dateless_task():
    s = svc()
    t = _task(s)
    assert task_reminders.sync_for_task(s, t, timezone_name="UTC") is None
    assert s.list_reminders(1) == ()


def test_adding_a_task_whose_reminder_moment_has_passed_schedules_nothing():
    """A 2pm task added at 1:50pm with a 30-minute offset has no reminder to
    give. The confirmation email still goes out, so this is not silence."""
    s = svc()
    t = _task(s, due_date=date(2020, 1, 1), due_time=time(15, 0),
              reminder_minutes_before=30)
    assert task_reminders.sync_for_task(s, t, timezone_name="UTC") is None
    assert not any(r.status == ReminderStatus.SCHEDULED for r in s.list_reminders(1))
