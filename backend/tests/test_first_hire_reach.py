"""The first-hire questions reach the founder they were written for, and only
them.

TWO DEFECTS, ONE BANK. b48e5c12d709 added twenty questions for a founder who
has not hired anyone yet. Both of these were true of them the day they shipped:

  * They were offered to EVERYONE at Stage 0->1. They carried
    `min_team_size = 'solo'`, which is the widest band and admits every founder,
    so somebody with twelve staff was a candidate for "What would you need to
    see before you felt safe paying someone a salary?" -- a decision they made
    years ago. This is the `min_team_size` defect seen from the other side, and
    c92a41f7b508 adds `max_team_size` to say it.

  * They were asked to NOBODY. Measured on a full 30-question diagnosis for a
    solo founder at Validation: 0 of the 20. They are universal content, so
    `relevance_ranker` scores them UNIVERSAL_RANK, and the founder's own
    industry questions won every round ahead of them. Exactly the defect
    fae1f65c found in the Exit bank, so it takes the same fix, generalised:
    content written for this founder in particular ranks with content written
    for their industry.

WHY THE SECOND ONE HID. Every test around these questions asserted
REACHABILITY -- in the pool, admitted by the gate, not withheld by a scope --
and reachability was never what was broken. `is_written_for_band` is the
promotion the ranking reads, so it is what these tests pin.
"""

from types import SimpleNamespace

import pytest

from app.api.v1.diagnosis.team_scope import can_answer, gate, is_written_for_band

SOLO, SMALL, MID, LARGE = "solo", "2_5", "6_10", "11_25"


def _q(qid, *, min_team_size=None, max_team_size=None):
    return SimpleNamespace(
        question_id=qid,
        min_team_size=min_team_size,
        max_team_size=max_team_size,
    )


def _founder(team_size):
    return SimpleNamespace(founder_id=1, team_size=team_size)


# ---------------------------------------------------------------- the bound

def test_a_first_hire_question_reaches_a_founder_working_alone():
    assert can_answer(SOLO, SOLO, SOLO) is True


@pytest.mark.parametrize("band", [SMALL, MID, LARGE, "26_plus"])
def test_it_is_withheld_from_everyone_who_has_already_hired(band):
    """The defect this column exists for. A founder with staff answered this
    question years ago; putting it to them describes a company that does not
    exist."""
    assert can_answer(SOLO, band, SOLO) is False


def test_the_two_bounds_are_read_independently():
    """A window, not a single comparison. Nothing in the live bank carries both
    today, and the reader must still be right if something does."""
    window = dict(min_team_size=SMALL, max_team_size=MID)
    assert can_answer(band=SMALL, **window) is True
    assert can_answer(band=MID, **window) is True
    assert can_answer(band=SOLO, **window) is False     # below the floor
    assert can_answer(band=LARGE, **window) is False    # above the ceiling


# ------------------------------------------------------------- failing open

def test_an_unknown_team_size_is_narrowed_by_neither_bound():
    """Every founder who onboarded before 2026-09-28 has NULL. Absence of a
    fact is never evidence for withholding."""
    assert can_answer(SOLO, None, SOLO) is True

    first_hire = _q(1, max_team_size=SOLO)
    assert gate([first_hire], _founder(None)) == [first_hire]


@pytest.mark.parametrize("junk", ["", "  ", "enormous", 7, 2.5, object()])
def test_an_unreadable_ceiling_narrows_nobody(junk):
    """A CHECK guards the column, but a migration or a hand-edit could still
    write something else, and a bad row must not shrink a diagnosis."""
    assert can_answer(None, LARGE, junk) is True


def test_a_question_that_cannot_say_whether_it_has_a_ceiling_has_none():
    """The candidate objects in these tests are the shape the engine's other
    ranking terms tolerate, so the gate must tolerate it too."""
    bare = SimpleNamespace(question_id=1)
    assert gate([bare], _founder(LARGE)) == [bare]
    assert is_written_for_band(bare) is False


def test_the_gate_never_empties_a_non_empty_set():
    """Ending a founder's diagnosis early over a data problem is worse than
    asking one question they cannot answer."""
    only_first_hire = [_q(1, max_team_size=SOLO), _q(2, max_team_size=SOLO)]
    kept = gate(only_first_hire, _founder(LARGE))
    assert kept == only_first_hire


# --------------------------------------------------------------- the ranking

def test_a_bounded_question_is_promoted_to_the_founders_own_content():
    assert is_written_for_band(_q(1, max_team_size=SOLO)) is True


def test_an_unbounded_question_is_not():
    assert is_written_for_band(_q(1)) is False


def test_the_pillar_wide_min_team_size_default_promotes_nothing():
    """The distinction the whole promotion rests on. 1,031 Team & Leadership
    questions carry `min_team_size = '2_5'` because it is that pillar's reviewed
    default, not because anyone aimed them at a five-person company. Promote on
    that and half the pillar outranks industry content for every founder
    alive."""
    pillar_default = _q(1, min_team_size=SMALL)
    assert is_written_for_band(pillar_default) is False
