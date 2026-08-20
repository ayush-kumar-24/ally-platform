"""Domain tests for the Achievements module. In-memory, deterministic, offline."""

from datetime import datetime, timedelta, timezone
from itertools import count

import pytest

from app.achievements import (
    AchievementNotFoundError,
    AchievementsLockedError,
    InMemoryAchievementRepository,
    InvalidAchievementInputError,
    build_achievement_service,
)

T0 = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)


class StepClock:
    def __init__(self, start=T0, step=timedelta(seconds=1)):
        self._now, self._step = start, step

    def __call__(self):
        v = self._now
        self._now += self._step
        return v


def svc(unlocked_founder_id=1, message_count=20):
    """By default, founder 1 is past the unlock threshold -- most tests care
    about achievement CRUD, not the gate itself (which has its own tests)."""
    repo = InMemoryAchievementRepository({unlocked_founder_id: message_count})
    c = count(1)
    return build_achievement_service(repo, clock=StepClock(), id_factory=lambda: f"a-{next(c)}")


# --- engagement gate ---------------------------------------------------


def test_engagement_reflects_real_message_count():
    repo = InMemoryAchievementRepository({1: 7})
    s = build_achievement_service(repo)
    e = s.get_engagement(1)
    assert e.message_count == 7 and e.threshold == 15 and e.unlocked is False


def test_engagement_unlocked_at_threshold():
    repo = InMemoryAchievementRepository({1: 15})
    s = build_achievement_service(repo)
    assert s.get_engagement(1).unlocked is True


def test_engagement_zero_for_founder_with_no_conversations():
    s = build_achievement_service(InMemoryAchievementRepository())
    e = s.get_engagement(1)
    assert e.message_count == 0 and e.unlocked is False


def test_create_blocked_when_locked():
    s = build_achievement_service(InMemoryAchievementRepository({1: 5}))
    with pytest.raises(AchievementsLockedError):
        s.create_achievement(1, title="Crossed ₹1Cr ARR")


def test_create_allowed_once_unlocked():
    s = build_achievement_service(InMemoryAchievementRepository({1: 15}))
    a = s.create_achievement(1, title="Crossed ₹1Cr ARR")
    assert a.title == "Crossed ₹1Cr ARR"


def test_custom_unlock_threshold():
    s = build_achievement_service(InMemoryAchievementRepository({1: 3}), unlock_threshold=3)
    assert s.get_engagement(1).unlocked is True
    s.create_achievement(1, title="ok")  # does not raise


# --- creation -------------------------------------------------------------


def test_create_achievement_stores_all_fields():
    s = svc()
    a = s.create_achievement(1, title="Crossed ₹1Cr ARR", description="Built the first repeatable engine.",
                             category="Business", occurred_on="2022")
    assert a.achievement_id == "a-1"
    assert a.founder_id == 1
    assert a.title == "Crossed ₹1Cr ARR"
    assert a.description == "Built the first repeatable engine."
    assert a.category == "Business" and a.occurred_on == "2022"
    assert a.created_at == T0 and a.updated_at == T0


def test_optional_fields_default_empty():
    a = svc().create_achievement(1, title="Zero-attrition year")
    assert a.description == "" and a.category == "" and a.occurred_on == ""


def test_title_is_trimmed():
    a = svc().create_achievement(1, title="  Hired the first ops leader  ")
    assert a.title == "Hired the first ops leader"


@pytest.mark.parametrize("bad_title", ["", "   ", "\t\n"])
def test_empty_title_rejected(bad_title):
    with pytest.raises(InvalidAchievementInputError):
        svc().create_achievement(1, title=bad_title)


def test_overlong_title_rejected():
    with pytest.raises(InvalidAchievementInputError):
        svc().create_achievement(1, title="x" * 201)


def test_overlong_description_rejected():
    with pytest.raises(InvalidAchievementInputError):
        svc().create_achievement(1, title="ok", description="x" * 1001)


# --- listing ----------------------------------------------------------


def test_list_newest_first():
    s = svc()
    first = s.create_achievement(1, title="first")
    second = s.create_achievement(1, title="second")
    items = s.list_achievements(1)
    assert [a.achievement_id for a in items] == [second.achievement_id, first.achievement_id]


def test_founder_isolation_on_list():
    s = svc()
    s.create_achievement(1, title="founder 1's win")
    assert s.list_achievements(2) == ()


# --- updates ------------------------------------------------------------


def test_update_changes_only_provided_fields():
    s = svc()
    a = s.create_achievement(1, title="Original", description="v1", category="Business")
    updated = s.update_achievement(1, a.achievement_id, description="v2")
    assert updated.title == "Original" and updated.category == "Business"
    assert updated.description == "v2"
    assert updated.created_at == a.created_at
    assert updated.updated_at != a.updated_at


def test_update_wrong_founder_raises_not_found():
    s = svc()
    a = s.create_achievement(1, title="mine")
    with pytest.raises(AchievementNotFoundError):
        s.update_achievement(2, a.achievement_id, title="hijacked")
    assert s.list_achievements(1)[0].title == "mine"


def test_update_nonexistent_raises_not_found():
    with pytest.raises(AchievementNotFoundError):
        svc().update_achievement(1, "does-not-exist", title="x")


def test_update_is_not_gated_by_engagement():
    """Once legitimately created, editing an achievement doesn't re-check the
    gate -- a founder's engagement dropping later shouldn't lock them out of
    their own existing records."""
    repo = InMemoryAchievementRepository({1: 15})
    s = build_achievement_service(repo)
    a = s.create_achievement(1, title="mine")
    repo.set_message_count(1, 0)  # engagement "drops"
    updated = s.update_achievement(1, a.achievement_id, title="still editable")
    assert updated.title == "still editable"


# --- deletion -----------------------------------------------------------


def test_delete_removes_it():
    s = svc()
    a = s.create_achievement(1, title="to delete")
    s.delete_achievement(1, a.achievement_id)
    assert s.list_achievements(1) == ()


def test_delete_wrong_founder_raises_not_found_and_survives():
    s = svc()
    a = s.create_achievement(1, title="mine")
    with pytest.raises(AchievementNotFoundError):
        s.delete_achievement(2, a.achievement_id)
    assert len(s.list_achievements(1)) == 1


def test_delete_nonexistent_raises_not_found():
    with pytest.raises(AchievementNotFoundError):
        svc().delete_achievement(1, "does-not-exist")


# --- determinism --------------------------------------------------------


def test_deterministic_execution():
    def run():
        s = svc()
        s.create_achievement(1, title="a")
        s.create_achievement(1, title="b")
        return [(a.title, a.created_at) for a in s.list_achievements(1)]
    assert run() == run()
