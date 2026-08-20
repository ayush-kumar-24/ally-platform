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
