"""Domain tests for the Founder Goals module. In-memory, deterministic, offline."""

from datetime import datetime, timedelta, timezone
from itertools import count

import pytest

from app.founder_goals import (
    FounderGoalNotFoundError,
    InvalidFounderGoalInputError,
    build_founder_goal_service,
)

T0 = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)


class StepClock:
    def __init__(self, start=T0, step=timedelta(seconds=1)):
        self._now, self._step = start, step

    def __call__(self):
        v = self._now
        self._now += self._step
        return v


def svc():
    c = count(1)
    return build_founder_goal_service(clock=StepClock(), id_factory=lambda: f"g-{next(c)}")


# --- creation -----------------------------------------------------------


def test_create_goal_stores_all_fields():
    s = svc()
    g = s.create_goal(1, title="₹5Cr annual revenue", subtitle="₹3.4Cr achieved · due 31 Mar 2027")
    assert g.goal_id == "g-1"
    assert g.founder_id == 1
    assert g.title == "₹5Cr annual revenue"
    assert g.subtitle == "₹3.4Cr achieved · due 31 Mar 2027"
    assert g.created_at == T0 and g.updated_at == T0


def test_subtitle_is_optional():
    g = svc().create_goal(1, title="Four focused days a week")
    assert g.subtitle == ""


def test_title_is_trimmed():
    g = svc().create_goal(1, title="  Retention at 80%  ")
    assert g.title == "Retention at 80%"


@pytest.mark.parametrize("bad_title", ["", "   ", "\t\n"])
def test_empty_title_rejected(bad_title):
    with pytest.raises(InvalidFounderGoalInputError):
        svc().create_goal(1, title=bad_title)


def test_overlong_title_rejected():
    with pytest.raises(InvalidFounderGoalInputError):
        svc().create_goal(1, title="x" * 201)


def test_overlong_subtitle_rejected():
    with pytest.raises(InvalidFounderGoalInputError):
        svc().create_goal(1, title="ok", subtitle="x" * 501)


# --- listing --------------------------------------------------------------


def test_list_goals_newest_first():
    s = svc()
    first = s.create_goal(1, title="first")
    second = s.create_goal(1, title="second")
    items = s.list_goals(1)
    assert [g.goal_id for g in items] == [second.goal_id, first.goal_id]


def test_list_goals_empty_for_new_founder():
    assert svc().list_goals(1) == ()


def test_founder_isolation_on_list():
    s = svc()
    s.create_goal(1, title="founder 1's goal")
    assert s.list_goals(2) == ()


# --- updates ----------------------------------------------------------------


def test_update_goal_changes_only_provided_fields():
    s = svc()
    g = s.create_goal(1, title="Original", subtitle="Original subtitle")
    updated = s.update_goal(1, g.goal_id, subtitle="New subtitle")
    assert updated.title == "Original"           # untouched
    assert updated.subtitle == "New subtitle"
    assert updated.created_at == g.created_at     # preserved
    assert updated.updated_at != g.updated_at      # bumped


def test_update_goal_wrong_founder_raises_not_found():
    s = svc()
    g = s.create_goal(1, title="mine")
    with pytest.raises(FounderGoalNotFoundError):
        s.update_goal(2, g.goal_id, title="hijacked")
    # And the original is untouched.
    assert s.list_goals(1)[0].title == "mine"


def test_update_nonexistent_goal_raises_not_found():
    with pytest.raises(FounderGoalNotFoundError):
        svc().update_goal(1, "does-not-exist", title="x")


def test_update_rejects_empty_title():
    s = svc()
    g = s.create_goal(1, title="ok")
    with pytest.raises(InvalidFounderGoalInputError):
        s.update_goal(1, g.goal_id, title="   ")


# --- deletion -----------------------------------------------------------


def test_delete_goal_removes_it():
    s = svc()
    g = s.create_goal(1, title="to delete")
    s.delete_goal(1, g.goal_id)
    assert s.list_goals(1) == ()


def test_delete_wrong_founder_raises_not_found_and_does_not_delete():
    s = svc()
    g = s.create_goal(1, title="mine")
    with pytest.raises(FounderGoalNotFoundError):
        s.delete_goal(2, g.goal_id)
    assert len(s.list_goals(1)) == 1               # still there


def test_delete_nonexistent_goal_raises_not_found():
    with pytest.raises(FounderGoalNotFoundError):
        svc().delete_goal(1, "does-not-exist")


# --- determinism --------------------------------------------------------


def test_deterministic_execution():
    def run():
        s = svc()
        s.create_goal(1, title="a")
        s.create_goal(1, title="b")
        return [(g.title, g.created_at) for g in s.list_goals(1)]
    assert run() == run()


# --- completion, and the achievement it writes -----------------------------

class RecordingAchievements:
    """Stands in for AchievementService. Records what it was asked to write,
    so the tests below can assert the transition rule rather than the wording."""

    def __init__(self, fail=False):
        self.created = []
        self._fail = fail

    def create_achievement(self, founder_id, **kw):
        if self._fail:
            raise RuntimeError("achievements is down")
        self.created.append((founder_id, kw))
        return object()


def test_completing_a_goal_writes_one_achievement():
    ach = RecordingAchievements()
    s = build_founder_goal_service(clock=StepClock(), id_factory=lambda: "g-1",
                                   achievements=ach)
    g = s.create_goal(7, title="₹5Cr annual revenue", subtitle="₹3.4Cr today")

    done = s.set_completed(7, g.goal_id, True)

    assert done.is_completed and done.completed_at is not None
    assert len(ach.created) == 1
    founder_id, kw = ach.created[0]
    assert founder_id == 7
    assert kw["title"] == "₹5Cr annual revenue"
    assert kw["category"] == "Goal reached"
    # Earned, not authored: it must not be refused by the engagement gate that
    # applies to hand-written entries.
    assert kw["earned"] is True


def test_completing_twice_does_not_write_a_second_achievement():
    """The guard that makes this safe to call from a double-tap, a retried
    request, or anything else that can fire the same intent more than once."""
    ach = RecordingAchievements()
    s = build_founder_goal_service(clock=StepClock(), id_factory=lambda: "g-1",
                                   achievements=ach)
    g = s.create_goal(7, title="Hire an ops lead")

    first = s.set_completed(7, g.goal_id, True)
    again = s.set_completed(7, g.goal_id, True)

    assert len(ach.created) == 1
    # Unchanged, not re-stamped with a later time.
    assert again.completed_at == first.completed_at


def test_reopening_clears_completion_but_keeps_the_achievement():
    ach = RecordingAchievements()
    s = build_founder_goal_service(clock=StepClock(), id_factory=lambda: "g-1",
                                   achievements=ach)
    g = s.create_goal(7, title="Retention at 80%")
    s.set_completed(7, g.goal_id, True)

    reopened = s.set_completed(7, g.goal_id, False)

    assert not reopened.is_completed and reopened.completed_at is None
    # It was reached on that date. Raising the bar afterwards does not undo it.
    assert len(ach.created) == 1


def test_reaching_it_again_after_reopening_writes_a_second():
    """Not a duplicate: the founder hit it, moved the goalposts, and hit it
    again. Both are real, and the transition rule is what tells them apart."""
    ach = RecordingAchievements()
    s = build_founder_goal_service(clock=StepClock(), id_factory=lambda: "g-1",
                                   achievements=ach)
    g = s.create_goal(7, title="₹5Cr annual revenue")
    s.set_completed(7, g.goal_id, True)
    s.set_completed(7, g.goal_id, False)
    s.set_completed(7, g.goal_id, True)
    assert len(ach.created) == 2


def test_a_failing_achievements_service_does_not_lose_the_completion():
    """The goal is the founder's own record of their work. A bookkeeping
    problem on another page must not tell them it did not happen."""
    s = build_founder_goal_service(clock=StepClock(), id_factory=lambda: "g-1",
                                   achievements=RecordingAchievements(fail=True))
    g = s.create_goal(7, title="Ship the beta")

    done = s.set_completed(7, g.goal_id, True)

    assert done.is_completed
    assert s.list_goals(7)[0].is_completed


def test_completion_works_with_no_achievements_service_wired():
    s = svc()
    g = s.create_goal(7, title="Ship the beta")
    assert s.set_completed(7, g.goal_id, True).is_completed


def test_another_founders_goal_cannot_be_completed():
    s = svc()
    g = s.create_goal(7, title="Mine")
    with pytest.raises(FounderGoalNotFoundError):
        s.set_completed(8, g.goal_id, True)


def test_a_new_goal_starts_open():
    s = svc()
    assert not s.create_goal(7, title="Anything").is_completed
