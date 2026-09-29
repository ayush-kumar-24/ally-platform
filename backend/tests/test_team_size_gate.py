"""Team-size gating: whether there is anybody for the question to be about.

The reported failure, in the founder's words: the diagnosis asks people
building alone about how their team communicates and how they delegate.

The mechanics behind it. `founders.team_size` existed from the first schema and
nothing ever asked for it, so every row was NULL; and nothing in `questions`
recorded which questions need other people. So a founder at Validation working
alone was a valid candidate for "Can your staff agree a discount without asking
you?" and "When you last hired, how did you check they could do the work?".
They answer nothing, or apologise, and `business_health` scores that as a gap --
so working alone reads back to them as failing at leadership.

Three things had to be true to fix it, and all three are tested here:

  * The gate withholds a question the founder has nobody to answer about.
  * It withholds NOTHING when the founder's size is unknown. Every founder who
    onboarded before 2026-09-28 has NULL, and narrowing them would shrink every
    one of their diagnoses -- worst in the very pillar this protects.
  * It never empties the candidate set, whatever the data says. Ending a
    diagnosis early over a bad row is worse than one unanswerable question.

The bands below are the real ones from founders_team_size_check.
"""

from types import SimpleNamespace

import pytest

from app.api.v1.diagnosis.team_scope import (
    TEAM_SIZE_ORDER,
    can_answer,
    gate,
    team_size_of,
)

SOLO, SMALL, MID, LARGE = "solo", "2_5", "6_10", "11_25"


def _q(qid, min_team_size=None):
    return SimpleNamespace(question_id=qid, min_team_size=min_team_size)


def _founder(team_size):
    return SimpleNamespace(founder_id=1, team_size=team_size)


# Shaped like the real bank after d4a1f8c62b73 and f1b6d93ac274: most questions
# carry no requirement, Team & Leadership defaults to '2_5', a reviewed few are
# open to 'solo', and the ones presupposing managers sit at '11_25'.
ANY_A, ANY_B = 101, 102            # not Team & Leadership -- no requirement
TL_SOLO = 201                      # "is anyone pressure-testing your decisions?"
TL_TEAM_A, TL_TEAM_B = 202, 203    # "can your staff approve a discount?"
TL_ORG = 204                       # "leading through managers instead of directly"

BANK = [
    _q(ANY_A), _q(ANY_B),
    _q(TL_SOLO, SOLO),
    _q(TL_TEAM_A, SMALL), _q(TL_TEAM_B, SMALL),
    _q(TL_ORG, LARGE),
]


def _kept(founder):
    return {q.question_id for q in gate(list(BANK), founder)}


# --- the defect ------------------------------------------------------------

def test_a_founder_working_alone_is_not_asked_about_their_staff():
    kept = _kept(_founder(SOLO))
    assert TL_TEAM_A not in kept and TL_TEAM_B not in kept
    assert TL_ORG not in kept


def test_a_founder_working_alone_still_gets_the_questions_written_for_them():
    kept = _kept(_founder(SOLO))
    assert TL_SOLO in kept, "the solo tier is the whole point of the gate"
    assert {ANY_A, ANY_B} <= kept, "gating team size must not touch other pillars"


def test_a_small_team_is_not_asked_about_layers_of_management():
    """The same defect one size up. Before this, every Team & Leadership
    question sat at '2_5', so a three-person company was asked about leading
    through managers and succession planning."""
    kept = _kept(_founder(SMALL))
    assert TL_ORG not in kept
    assert {TL_SOLO, TL_TEAM_A, TL_TEAM_B} <= kept


def test_a_larger_company_is_asked_everything():
    assert _kept(_founder(LARGE)) == {q.question_id for q in BANK}


@pytest.mark.parametrize("band", TEAM_SIZE_ORDER)
def test_every_band_can_answer_a_question_with_no_requirement(band):
    assert {ANY_A, ANY_B} <= _kept(_founder(band))


# --- fail open -------------------------------------------------------------

def test_an_unknown_team_size_withholds_nothing():
    """Every founder who onboarded before the question existed has NULL here.
    Gating them would shrink every one of their diagnoses."""
    assert _kept(_founder(None)) == {q.question_id for q in BANK}


@pytest.mark.parametrize("value", ["", "  ", "two", "SOLO", "6-10", 5, object()])
def test_an_unreadable_team_size_withholds_nothing(value):
    """The column has a CHECK, but a hand-edit or a bad migration could still
    put something else there. A bad row must not narrow a diagnosis."""
    assert team_size_of(_founder(value)) is None
    assert _kept(_founder(value)) == {q.question_id for q in BANK}


def test_a_question_requiring_an_unknown_band_is_admitted():
    """Absence of a fact is never evidence for withholding -- the same reading
    `_in_scope` gives an unmapped dimension."""
    odd = [_q(ANY_A), _q(999, "a_hundred_people")]
    assert {q.question_id for q in gate(odd, _founder(SOLO))} == {ANY_A, 999}


def test_the_gate_never_empties_the_candidate_set():
    """If every candidate needs a team the founder does not have, the gate
    hands the set back rather than ending the diagnosis. Ending it early over a
    data problem is worse than one unanswerable question."""
    only_team = [_q(TL_TEAM_A, SMALL), _q(TL_TEAM_B, SMALL), _q(TL_ORG, LARGE)]
    assert len(gate(only_team, _founder(SOLO))) == 3


def test_an_empty_candidate_set_stays_empty():
    assert gate([], _founder(SOLO)) == []


# --- the comparison itself -------------------------------------------------

def test_a_founder_can_answer_anything_at_or_below_their_own_band():
    for i, band in enumerate(TEAM_SIZE_ORDER):
        for required in TEAM_SIZE_ORDER[: i + 1]:
            assert can_answer(required, band), f"{band} should answer {required}"
        for required in TEAM_SIZE_ORDER[i + 1:]:
            assert not can_answer(required, band), f"{band} should not answer {required}"


def test_the_band_order_matches_the_column_it_compares():
    from typing import get_args

    from app.schemas.founder import TeamSize

    assert TEAM_SIZE_ORDER == get_args(TeamSize)


# --- wired into the engine -------------------------------------------------

def test_the_engine_applies_the_gate_outside_the_stage_scope_shortcut():
    """From Growth onward `scope.withholds_nothing` is true and `_in_scope`
    returns early. A founder at Growth working alone is exactly the case this
    gate exists for, so it has to run BEFORE that return -- the same placement
    the context and industry gates need, and for the same reason."""
    import inspect

    from app.api.v1.diagnosis.engine import QuestionSelectionEngine

    source = inspect.getsource(QuestionSelectionEngine._in_scope)
    gate_at = source.index("team_size_gate(")
    # The short-circuit itself, not the earlier comment that explains why the
    # context gate has to sit outside it.
    shortcut_at = source.index("if scope is None or scope.withholds_nothing")
    assert gate_at < shortcut_at, (
        "the team-size gate runs after the stage-scope short-circuit, so a "
        "solo founder at Growth is still asked about their staff"
    )
