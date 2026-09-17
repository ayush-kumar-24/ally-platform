"""Fundraising context gating: whether the SUBJECT is this founder's at all.

The failure these exist to stop, reproduced live in the ComplyFlow QA run: a
B2B SaaS founder who never mentioned investors was asked about investor
materials, and the diagnosis recommended building a deck.

Measured cause, not guessed: from stage_order 2 upward `withheld_categories` is
empty, so all 101 Fundraising questions are eligible for everyone, and the
pillar round-robin then PROMOTES them -- the seven FND problems carry
`pillar_id = 6` (Strategic Clarity), where Fundraising is one of only four
categories at Stage 0->1, so the coverage mechanism guarantees it a turn.

The gate is at PROBLEM grain, never category and never question id. Six of the
seven FND problems presuppose a raise; FND-005 "Weak Pitch and Story" does not,
and the tests below spend as much effort proving FND-005 survives as proving the
other six are withheld. A gate that took the pitch battery with it would have
traded one wrong behaviour for another.
"""

import contextlib
from types import SimpleNamespace

import pytest

from app.api.v1.diagnosis.context_scope import (
    FUNDRAISING_CHALLENGE,
    FUNDRAISING_INTENT,
    PROBLEM_PRECONDITIONS,
    context_tokens,
    gated_problem_codes,
)
from app.api.v1.diagnosis.engine import QuestionSelectionEngine

STRATEGIC_CLARITY = 6

#: The real shape: every FND problem sits in pillar 6 alongside the three other
#: Strategic Clarity categories it round-robins against.
_PROBLEM_CODE = {
    301: "FND-001", 302: "FND-002", 303: "FND-003", 304: "FND-004",
    305: "FND-005", 306: "FND-006", 307: "FND-007",
    401: "RSK-001", 402: "PLN-001", 403: "OPP-001",
}
_PILLAR_MAP = {pid: STRATEGIC_CLARITY for pid in _PROBLEM_CODE}

_GATED_PROBLEM_IDS = {301, 302, 303, 304, 306, 307}
_FND_005 = 305

#: Q282 by its real id, so a rename of the fixture cannot quietly stop testing
#: the question this gate was designed around.
Q282 = 282


def _q(qid, problem_id, category="Fundraising", priority="CORE", difficulty=1):
    return SimpleNamespace(
        question_id=qid, problem_id=problem_id, root_cause_id=None,
        category=category, priority=priority, difficulty_level=difficulty,
    )


#: One question per FND problem, plus Q282 under FND-005 and the three
#: non-fundraising pillar-6 categories that must absorb the freed budget.
_BANK = [
    _q(1001, 301), _q(1002, 302), _q(1003, 303), _q(1004, 304),
    _q(Q282, _FND_005), _q(1005, _FND_005),
    _q(1006, 306), _q(1007, 307),
    _q(2001, 401, "Risk Identification"),
    _q(2002, 402, "Business Planning"),
    _q(2003, 403, "Opportunity Evaluation"),
]


def _founder(stage_order=2, **kwargs):
    """`current_challenges` is only set when a test passes it, so the default
    founder exercises the unknown/fail-open path the way a pre-onboarding row
    actually would."""
    stage = SimpleNamespace(stage_order=stage_order) if stage_order else None
    return SimpleNamespace(founder_id=1, stage=stage, **kwargs)


def _engine(candidates=None, *, code_map=None, code_map_raises=False):
    def problem_to_code():
        if code_map_raises:
            raise RuntimeError("db down")
        return dict(_PROBLEM_CODE if code_map is None else code_map)

    fake_db = SimpleNamespace(begin_nested=lambda: contextlib.nullcontext())
    return QuestionSelectionEngine(SimpleNamespace(
        db=fake_db,
        list_candidate_questions=lambda **kw: list(
            _BANK if candidates is None else candidates),
        problem_to_pillar=lambda: dict(_PILLAR_MAP),
        problem_to_dimension=lambda: {},
        problem_to_code=problem_to_code,
        answered_count_per_pillar_category=lambda session_id: {},
        get_detected_root_cause_ids=lambda session_id: set(),
    ))


def _session():
    return SimpleNamespace(session_id=1, routing_state="continue")


def _problem_ids(questions):
    return {q.problem_id for q in questions}


def _ask(founder, **engine_kwargs):
    return _engine(**engine_kwargs).candidate_questions(_session(), founder)


# --- 1. the founder who is not raising --------------------------------------

def test_a_non_fundraising_founder_is_not_asked_the_six_gated_problems():
    got = _problem_ids(_ask(_founder(current_challenges=["Sales", "Cash flow"])))
    assert not (got & _GATED_PROBLEM_IDS)


def test_cash_flow_worry_is_not_read_as_fundraising_intent():
    """`impression.facts` groups "Cash flow" with "Fundraising" as MONEY
    CHALLENGES. That grouping is about tone and must not leak into eligibility:
    most founders worried about cash are not raising."""
    got = _problem_ids(_ask(_founder(current_challenges=["Cash flow"])))
    assert not (got & _GATED_PROBLEM_IDS)


# --- 2. the founder who IS raising ------------------------------------------

def test_a_fundraising_founder_still_gets_all_seven_problems():
    got = _problem_ids(_ask(_founder(current_challenges=["Sales", "Fundraising"])))
    assert _GATED_PROBLEM_IDS <= got
    assert _FND_005 in got


def test_the_label_is_matched_whole_and_case_insensitively():
    """An exact label comparison, never a substring. "Fundraising timeline"
    typed into `current_challenges_other` must not open the gate, or the
    behaviour depends on free text a founder wrote."""
    assert context_tokens(_founder(current_challenges=["fundraising"])) == \
        frozenset({FUNDRAISING_INTENT})
    assert context_tokens(_founder(current_challenges=["  Fundraising  "])) == \
        frozenset({FUNDRAISING_INTENT})
    assert context_tokens(_founder(current_challenges=["Fundraising timeline"])) \
        == frozenset()


# --- 3 & 6. FND-005 is never gated ------------------------------------------

def test_fnd_005_survives_for_a_founder_who_is_not_raising():
    """The point of gating at problem grain. Explaining your business to a
    capable outsider is universal; a category-level gate would have taken this
    whole battery with it."""
    got = _ask(_founder(current_challenges=["Sales"]))
    assert _FND_005 in _problem_ids(got)


def test_q282_specifically_survives_for_a_founder_who_is_not_raising():
    got = _ask(_founder(current_challenges=["Sales"]))
    assert Q282 in {q.question_id for q in got}


@pytest.mark.parametrize("stage_order", [2, 3, 4])
def test_fnd_005_survives_across_every_stage_0_to_1_stage(stage_order):
    got = _ask(_founder(stage_order, current_challenges=["Sales"]))
    assert _FND_005 in _problem_ids(got)
    assert not (_problem_ids(got) & _GATED_PROBLEM_IDS)


def test_fnd_005_is_absent_from_the_precondition_map():
    """A guard on the curated content, not on behaviour. If someone adds
    FND-005 here, the tests above still need to fail for the right reason --
    and this one names it."""
    assert "FND-005" not in PROBLEM_PRECONDITIONS
    assert set(PROBLEM_PRECONDITIONS) == {
        "FND-001", "FND-002", "FND-003", "FND-004", "FND-006", "FND-007"}
    assert set(PROBLEM_PRECONDITIONS.values()) == {FUNDRAISING_INTENT}


# --- 7. the stage that withholds nothing ------------------------------------

@pytest.mark.parametrize("stage_order", [5, 6, 7, 8])
def test_the_gate_applies_where_stage_scope_withholds_nothing(stage_order):
    """From Growth on, `scope.withholds_nothing` is True and `_in_scope` used to
    return immediately. The context gate runs BEFORE that short-circuit: a
    scaling founder who is not raising is not too early for fundraising
    questions, the subject is simply not theirs."""
    got = _problem_ids(_ask(_founder(stage_order, current_challenges=["Scaling"])))
    assert not (got & _GATED_PROBLEM_IDS)
    assert _FND_005 in got


def test_a_founder_with_no_stage_is_still_gated():
    """Context does not depend on stage resolving. `resolve_scope` returns None
    for a founder with no stage, which used to mean no filtering at all."""
    got = _problem_ids(_ask(_founder(None, current_challenges=["Sales"])))
    assert not (got & _GATED_PROBLEM_IDS)


# --- 4 & 5. fail open --------------------------------------------------------

@pytest.mark.parametrize("challenges", [
    pytest.param([], id="empty-list"),
    pytest.param(None, id="null"),
    pytest.param("Fundraising", id="bare-string"),
    pytest.param({"a": 1}, id="dict"),
    pytest.param([None, ""], id="list-of-blanks"),
    pytest.param(123, id="number"),
])
def test_an_unreadable_answer_fails_open(challenges):
    """Not ticking "Fundraising" is only weak evidence -- the question is
    "biggest challenge, pick up to three", and nothing in the schema means
    "bootstrapped". So the negative is honoured only when the founder actually
    answered, and never inferred from an empty or unreadable row."""
    assert context_tokens(_founder(current_challenges=challenges)) is None
    assert _GATED_PROBLEM_IDS <= _problem_ids(
        _ask(_founder(current_challenges=challenges)))


def test_a_founder_row_without_the_field_at_all_fails_open():
    assert context_tokens(_founder()) is None
    assert _GATED_PROBLEM_IDS <= _problem_ids(_ask(_founder()))


def test_an_exploding_founder_object_fails_open():
    """A gate that can raise would be able to end a diagnosis over a malformed
    profile row, which is strictly worse than asking about investors."""
    class Boom:
        founder_id = 1
        stage = SimpleNamespace(stage_order=2)

        @property
        def current_challenges(self):
            raise RuntimeError("bad row")

    assert context_tokens(Boom()) is None


# --- degrade paths -----------------------------------------------------------

def test_an_unavailable_code_map_disables_only_this_test():
    got = _problem_ids(
        _ask(_founder(current_challenges=["Sales"]), code_map_raises=True))
    assert _GATED_PROBLEM_IDS <= got


def test_a_problem_with_no_code_recorded_is_admitted():
    """Absence of a fact is never evidence for withholding -- the same reading
    the dimension test uses."""
    got = _problem_ids(_ask(_founder(current_challenges=["Sales"]),
                            code_map={305: "FND-005"}))
    assert _GATED_PROBLEM_IDS <= got


def test_the_gate_never_empties_a_non_empty_candidate_set():
    """The invariant `_in_scope` already held, restated for the filter that now
    runs before it. Ending a founder's diagnosis early is worse than asking an
    off-topic question."""
    only_gated = [_q(1001, 301), _q(1006, 306)]
    got = _ask(_founder(current_challenges=["Sales"]), candidates=only_gated)
    assert len(got) == 2


def test_an_empty_bank_stays_empty():
    assert _ask(_founder(current_challenges=["Sales"]), candidates=[]) == []


# --- 8. coverage and selection still work ------------------------------------

def test_pillar_6_coverage_does_not_collapse_when_fundraising_is_gated():
    """Strategic Clarity has three other categories at Stage 0->1 (Risk
    Identification 24, Business Planning 18, Operations & Systems 8 on the live
    bank), so freeing Fundraising's turn does not starve the pillar."""
    got = _ask(_founder(current_challenges=["Sales"]))
    categories = {q.category for q in got}
    assert {"Risk Identification", "Business Planning",
            "Opportunity Evaluation"} <= categories
    assert len(got) == len(_BANK) - len(_GATED_PROBLEM_IDS)


def test_selection_still_returns_a_question_for_a_gated_founder():
    engine = _engine()
    picked = engine.select_next_question(
        _session(), _founder(current_challenges=["Sales"]))
    assert picked is not None
    assert picked.problem_id not in _GATED_PROBLEM_IDS


def test_both_founders_are_offered_the_pitch_battery_first():
    """FND-005 leads pillar 6 for both, which is the behaviour to protect: the
    gate changes what is REACHABLE, not the order of what survives it."""
    engine = _engine()
    for challenges in (["Sales"], ["Fundraising"]):
        picked = engine.select_next_question(
            _session(), _founder(current_challenges=challenges))
        assert picked.problem_id == _FND_005


def test_only_the_fundraising_founder_can_ever_reach_the_gated_problems():
    """Walks the whole ordering rather than checking the head. The bias in
    `_sort_key_for` only reorders, so a filter that merely demoted these would
    still surface them at the budget tail -- which is the case a 30-question
    session actually reaches."""
    engine = _engine()

    def reachable(challenges):
        return _problem_ids(engine.candidate_questions(
            _session(), _founder(current_challenges=challenges)))

    assert not (reachable(["Sales"]) & _GATED_PROBLEM_IDS)
    assert _GATED_PROBLEM_IDS <= reachable(["Fundraising"])


# --- the mapping itself ------------------------------------------------------

def test_gated_codes_are_empty_for_an_unknown_context():
    assert gated_problem_codes(None) == frozenset()


def test_gated_codes_are_empty_when_the_token_is_held():
    assert gated_problem_codes(frozenset({FUNDRAISING_INTENT})) == frozenset()


def test_gated_codes_are_the_six_when_the_token_is_absent():
    assert gated_problem_codes(frozenset()) == {
        "FND-001", "FND-002", "FND-003", "FND-004", "FND-006", "FND-007"}


def test_the_onboarding_label_is_the_one_onboarding_actually_offers():
    """Mirrors frontend/src/data/onboardingQuestions.js. There is no CHECK
    constraint on `founders.current_challenges`, so this constant is the only
    thing tying the gate to the option a founder can actually pick."""
    assert FUNDRAISING_CHALLENGE == "Fundraising"
