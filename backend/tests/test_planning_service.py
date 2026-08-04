"""Domain tests for the Planning module (Founder Action Plans). In-memory, deterministic."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from itertools import count

import pytest

from app.planning import (
    GoalNotFoundError,
    InvalidPlanningInputError,
    ItemSource,
    PlanNotFoundError,
    PlanStatus,
    Priority,
    ProgressStatus,
    ReminderChannel,
    ReminderNotFoundError,
    ReminderStatus,
    TaskNotFoundError,
    build_planning_service,
)

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


# --- plans ------------------------------------------------------------------


def test_create_and_get_plan():
    s = svc()
    p = s.create_plan(1, title="Q3 Growth")
    assert p.status == PlanStatus.ACTIVE and p.founder_id == 1
    assert s.get_plan(1, p.plan_id).title == "Q3 Growth"


def test_get_plan_foreign_founder_not_found():
    s = svc()
    p = s.create_plan(1, title="Mine")
    with pytest.raises(PlanNotFoundError):
        s.get_plan(2, p.plan_id)                          # founder 2 can't see founder 1's plan


def test_create_plan_empty_title_rejected():
    with pytest.raises(InvalidPlanningInputError):
        svc().create_plan(1, title="   ")


def test_list_plans_excludes_archived_by_default():
    s = svc()
    a = s.create_plan(1, title="A")
    s.create_plan(1, title="B")
    s.archive_plan(1, a.plan_id)
    assert {p.title for p in s.list_plans(1)} == {"B"}
    assert {p.title for p in s.list_plans(1, include_archived=True)} == {"A", "B"}


def test_update_and_restore_plan():
    s = svc()
    p = s.create_plan(1, title="Old")
    assert s.update_plan(1, p.plan_id, title="New", status=PlanStatus.COMPLETED).title == "New"
    s.archive_plan(1, p.plan_id)
    assert s.restore_plan(1, p.plan_id).status == PlanStatus.ACTIVE


# --- goals + tasks ----------------------------------------------------------


def test_add_goal_and_task_hierarchy():
    s = svc()
    p = s.create_plan(1, title="Plan")
    g = s.add_goal(1, p.plan_id, title="Improve activation", priority=Priority.HIGH,
                   target_date=date(2026, 8, 15))
    t = s.add_task(1, g.goal_id, title="Interview 10 users", due_date=date(2026, 8, 1))
    assert g.plan_id == p.plan_id and g.priority == Priority.HIGH
    assert t.goal_id == g.goal_id and t.plan_id == p.plan_id
    assert [x.goal_id for x in s.list_goals(1, p.plan_id)] == [g.goal_id]
    assert [x.task_id for x in s.list_tasks(1, g.goal_id)] == [t.task_id]


def test_completing_task_stamps_and_clears_completed_at():
    s = svc()
    p = s.create_plan(1, title="Plan")
    g = s.add_goal(1, p.plan_id, title="G")
    t = s.add_task(1, g.goal_id, title="T")
    done = s.update_task(1, t.task_id, status=ProgressStatus.DONE)
    assert done.completed_at is not None
    reopened = s.update_task(1, t.task_id, status=ProgressStatus.TODO)
    assert reopened.completed_at is None


def test_clear_due_date():
    s = svc()
    p = s.create_plan(1, title="Plan")
    g = s.add_goal(1, p.plan_id, title="G")
    t = s.add_task(1, g.goal_id, title="T", due_date=date(2026, 8, 1))
    assert s.update_task(1, t.task_id, clear_due_date=True).due_date is None


def test_goal_and_task_ownership():
    s = svc()
    p = s.create_plan(1, title="Plan")
    g = s.add_goal(1, p.plan_id, title="G")
    t = s.add_task(1, g.goal_id, title="T")
    with pytest.raises(GoalNotFoundError):
        s.get_goal(2, g.goal_id)
    with pytest.raises(TaskNotFoundError):
        s.get_task(2, t.task_id)


def test_add_goal_to_foreign_plan_not_found():
    s = svc()
    p = s.create_plan(1, title="Plan")
    with pytest.raises(PlanNotFoundError):
        s.add_goal(2, p.plan_id, title="G")


# --- plan detail + diagnosis seeding ----------------------------------------


def test_plan_detail_nests_goals_and_tasks():
    s = svc()
    p = s.create_plan(1, title="Plan")
    g = s.add_goal(1, p.plan_id, title="G")
    s.add_task(1, g.goal_id, title="T1")
    s.add_task(1, g.goal_id, title="T2")
    detail = s.get_plan_detail(1, p.plan_id)
    assert detail.plan.plan_id == p.plan_id
    assert len(detail.goals) == 1 and len(detail.goals[0].tasks) == 2


def test_seed_from_diagnosis():
    s = svc()
    p = s.create_plan(1, title="Plan")
    seeded = s.seed_from_diagnosis(1, p.plan_id, ["Interview churned users", "  ", "Book a call"])
    assert seeded.goal.source == ItemSource.DIAGNOSIS and seeded.goal.title == "Diagnosis next steps"
    assert [t.title for t in seeded.tasks] == ["Interview churned users", "Book a call"]   # blanks skipped
    assert all(t.source == ItemSource.DIAGNOSIS for t in seeded.tasks)


# --- isolation / concurrency / determinism ----------------------------------


def test_founder_isolation():
    s = svc()
    s.create_plan(1, title="One")
    s.create_plan(2, title="Two")
    assert {p.title for p in s.list_plans(1)} == {"One"}
    assert {p.title for p in s.list_plans(2)} == {"Two"}


def test_concurrent_reads():
    s = svc()
    p = s.create_plan(1, title="Plan")
    for i in range(3):
        s.add_goal(1, p.plan_id, title=f"G{i}")

    def read(_):
        return len(s.list_goals(1, p.plan_id)) == 3

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert all(pool.map(read, range(40)))


def test_deterministic_execution():
    def run():
        s = svc()
        p = s.create_plan(1, title="Plan")
        g = s.add_goal(1, p.plan_id, title="G")
        s.add_task(1, g.goal_id, title="T")
        return s.get_plan_detail(1, p.plan_id)
    assert run() == run()


# --- progress (derived) -----------------------------------------------------
def test_plan_progress_derived_from_task_status():
    s = svc()
    p = s.create_plan(1, title="Q3")
    g = s.add_goal(1, p.plan_id, title="Ship onboarding")
    t1 = s.add_task(1, g.goal_id, title="a")
    s.add_task(1, g.goal_id, title="b")
    t3 = s.add_task(1, g.goal_id, title="c")
    s.update_task(1, t1.task_id, status=ProgressStatus.DONE)
    s.update_task(1, t3.task_id, status=ProgressStatus.IN_PROGRESS)
    prog = s.plan_progress(1, p.plan_id)
    assert prog.tasks.total == 3
    assert (prog.tasks.done, prog.tasks.in_progress, prog.tasks.todo) == (1, 1, 1)
    assert prog.tasks.percent_complete == 33
    assert len(prog.per_goal) == 1 and prog.per_goal[0].tasks.total == 3


def test_plan_progress_empty_is_zero_not_error():
    s = svc()
    p = s.create_plan(1, title="Empty")
    prog = s.plan_progress(1, p.plan_id)
    assert prog.tasks.total == 0 and prog.tasks.percent_complete == 0
    assert prog.per_goal == ()


def test_plan_progress_enforces_ownership():
    s = svc()
    p = s.create_plan(1, title="Mine")
    with pytest.raises(PlanNotFoundError):
        s.plan_progress(2, p.plan_id)


# --- reminders --------------------------------------------------------------
def _task_for(s):
    p = s.create_plan(1, title="P")
    g = s.add_goal(1, p.plan_id, title="G")
    return s.add_task(1, g.goal_id, title="T")

_FUTURE = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)


def test_schedule_and_list_reminder():
    s = svc()
    t = _task_for(s)
    r = s.schedule_reminder(1, t.task_id, remind_at=_FUTURE, note="ping")
    assert r.status == ReminderStatus.SCHEDULED and r.task_id == t.task_id and r.channel == ReminderChannel.IN_APP
    lst = s.list_reminders(1)
    assert len(lst) == 1 and lst[0].reminder_id == r.reminder_id


def test_schedule_reminder_past_time_rejected():
    s = svc()
    t = _task_for(s)
    with pytest.raises(InvalidPlanningInputError):
        s.schedule_reminder(1, t.task_id, remind_at=datetime(2020, 1, 1, tzinfo=timezone.utc))


def test_schedule_reminder_foreign_task_rejected():
    s = svc()
    t = _task_for(s)
    with pytest.raises(TaskNotFoundError):
        s.schedule_reminder(2, t.task_id, remind_at=_FUTURE)   # not founder 2's task


def test_cancel_reminder_and_ownership():
    s = svc()
    t = _task_for(s)
    r = s.schedule_reminder(1, t.task_id, remind_at=_FUTURE)
    with pytest.raises(ReminderNotFoundError):
        s.cancel_reminder(2, r.reminder_id)                    # another founder
    cancelled = s.cancel_reminder(1, r.reminder_id)
    assert cancelled.status == ReminderStatus.CANCELLED


def test_due_reminders_are_scheduled_and_past_only():
    s = svc()
    t = _task_for(s)
    r = s.schedule_reminder(1, t.task_id, remind_at=_FUTURE)
    ids = lambda rs: [x.reminder_id for x in rs]
    assert r.reminder_id in ids(s.due_reminders(before=datetime(2026, 8, 2, tzinfo=timezone.utc)))
    assert r.reminder_id not in ids(s.due_reminders(before=datetime(2026, 7, 31, tzinfo=timezone.utc)))  # not yet due
    s.cancel_reminder(1, r.reminder_id)
    assert r.reminder_id not in ids(s.due_reminders(before=datetime(2026, 8, 2, tzinfo=timezone.utc)))    # cancelled excluded


def test_mark_reminder_sent():
    s = svc()
    t = _task_for(s)
    r = s.schedule_reminder(1, t.task_id, remind_at=_FUTURE)
    sent = s.mark_reminder_sent(r.reminder_id)
    assert sent.status == ReminderStatus.SENT and sent.sent_at is not None
