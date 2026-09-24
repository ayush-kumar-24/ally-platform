"""RCCS: the normalised root-cause confidence score, its evidence model, and the
problem-driven completion / quality gate built on it.

Hermetic -- no database, no LLM, no clock. Every number here is arithmetic over
the module's own constants, so a failure means the model changed, not that an
environment drifted.

Test numbering follows the implementation brief's 30 required areas and its edge
cases; each test names the requirement it pins.
"""

from decimal import Decimal

import pytest

from app.api.v1.diagnosis.completion import (
    BANK_EXHAUSTED,
    PROBLEM_EXPLAINED,
    SAFETY_CEILING,
    decide_completion,
    evaluate_quality_gate,
)
from app.api.v1.diagnosis.rccs import (
    RCCS_STRONG_THRESHOLD,
    SIBLING_WEIGHT,
    EvidenceDirection,
    RCCSState,
    events_for_answer,
    format_rccs_percent,
)
from app.models.enums import ScoreLabel

RC_A, RC_B, RC_C = 101, 202, 303
PILLAR_1, PILLAR_2, PILLAR_3 = 1, 2, 3


def _answer(state, *, aid, band, rc=RC_A, pillar=PILLAR_1, siblings=(), qid=None):
    """Apply one classified answer and return the resulting score for `rc`."""
    events = events_for_answer(
        answer_id=aid,
        question_id=qid if qid is not None else 9000 + aid,
        score_label=band,
        primary_root_cause_id=rc,
        sibling_root_cause_ids=siblings,
        pillar_id=pillar,
        sequence=aid,
    )
    state.apply_all(events)
    return state.score_for(rc)


# --- 6, 7. RCCS exists and is normalised 0..1 ---------------------------------

def test_6_rccs_exists_and_is_computable():
    state = RCCSState()
    score = _answer(state, aid=1, band=ScoreLabel.RED)
    assert score.root_cause_id == RC_A
    assert isinstance(score.rccs, Decimal)


def test_7_rccs_stays_within_zero_and_one_under_extreme_evidence():
    """Neither a pile of support nor a pile of contradiction can leave [0,1]."""
    state = RCCSState()
    for i in range(1, 60):
        _answer(state, aid=i, band=ScoreLabel.RED, pillar=i % 7)
    assert Decimal(0) <= state.score_for(RC_A).rccs <= Decimal(1)

    state = RCCSState()
    for i in range(1, 60):
        _answer(state, aid=i, band=ScoreLabel.GREEN, pillar=i % 7)
    assert Decimal(0) <= state.score_for(RC_A).rccs <= Decimal(1)


def test_15_threshold_is_a_fraction_not_a_percentage():
    """0.80 means eighty percent. Not 80, not 0.008 -- the brief's explicit trap."""
    assert RCCS_STRONG_THRESHOLD == Decimal("0.80")
    assert Decimal("0.008") < RCCS_STRONG_THRESHOLD < Decimal(1)
    assert format_rccs_percent(Decimal("0.8342")) == "83%"
    assert format_rccs_percent(Decimal("0.80")) == "80%"


# --- 8, 9, 10, 11. Direction and incrementality --------------------------------

def test_8_supporting_evidence_increases_rccs():
    state = RCCSState()
    first = _answer(state, aid=1, band=ScoreLabel.RED).rccs
    second = _answer(state, aid=2, band=ScoreLabel.RED, pillar=PILLAR_2).rccs
    assert second > first


def test_9_corroboration_is_coverage_not_pillar_spread():
    """REWRITTEN FOR OPTION E, and the reversal is the point.

    This test previously asserted that evidence from a SECOND PILLAR outscored
    more evidence in the first. That was the absolute model's definition of
    corroboration, and it was measured to be unreachable: all 1,997 catalogue
    root causes have every one of their questions in a single pillar, so the
    cross-pillar branch could never fire in production.

    Under Option E corroboration means COVERAGE -- answering more of what the
    catalogue actually offers for this cause. Pillar spread no longer affects the
    primary signal, and the pillars touched are still recorded for the report.
    """
    askable = {RC_A: 2}
    one_pillar = RCCSState(askable=askable)
    _answer(one_pillar, aid=1, band=ScoreLabel.RED, pillar=PILLAR_1)
    _answer(one_pillar, aid=2, band=ScoreLabel.RED, pillar=PILLAR_1)

    two_pillars = RCCSState(askable=askable)
    _answer(two_pillars, aid=1, band=ScoreLabel.RED, pillar=PILLAR_1)
    _answer(two_pillars, aid=2, band=ScoreLabel.RED, pillar=PILLAR_2)

    assert one_pillar.score_for(RC_A).rccs == two_pillars.score_for(RC_A).rccs

    # Coverage IS what strengthens a cause now.
    partial = RCCSState(askable={RC_A: 4})
    _answer(partial, aid=1, band=ScoreLabel.RED, pillar=PILLAR_1)
    _answer(partial, aid=2, band=ScoreLabel.RED, pillar=PILLAR_1)
    assert partial.score_for(RC_A).rccs < one_pillar.score_for(RC_A).rccs


def test_10_contradictory_evidence_decreases_rccs():
    state = RCCSState()
    _answer(state, aid=1, band=ScoreLabel.RED)
    before = _answer(state, aid=2, band=ScoreLabel.RED, pillar=PILLAR_2).rccs
    after = _answer(state, aid=3, band=ScoreLabel.GREEN, pillar=PILLAR_3).rccs
    assert after < before


def test_11_rccs_updates_after_every_answer_and_the_trajectory_is_pinned():
    """REWRITTEN FOR OPTION E: the trajectory of a three-question cause.

    The old pinned trajectory (0.5000 / 0.6667 / 0.8333 / 0.7500 / 0.8000) came
    from the absolute model and from a worked example that assumed cross-pillar
    corroboration the catalogue cannot supply. What is pinned now is the
    coverage-relative shape: the score rises as more of the cause's AVAILABLE
    evidence is collected, crosses the threshold when the cause is fully probed
    and every probe was bad, and falls back when contradicted.
    """
    state = RCCSState(askable={RC_A: 3})
    seen = [
        _answer(state, aid=1, band=ScoreLabel.RED, pillar=PILLAR_1).rccs,
        _answer(state, aid=2, band=ScoreLabel.RED, pillar=PILLAR_1, qid=7002).rccs,
        _answer(state, aid=3, band=ScoreLabel.RED, pillar=PILLAR_1, qid=7003).rccs,
    ]
    assert seen == [Decimal("0.3077"), Decimal("0.6154"), Decimal("0.9231")]
    assert state.score_for(RC_A).is_strong

    # A contradiction arriving through a sibling edge pulls it back down.
    _answer(state, aid=4, band=ScoreLabel.GREEN, rc=RC_C, siblings=(RC_A,),
            pillar=PILLAR_2)
    assert state.score_for(RC_A).rccs < Decimal("0.9231")


def test_amber_supports_less_than_red():
    red = RCCSState()
    _answer(red, aid=1, band=ScoreLabel.RED)
    amber = RCCSState()
    _answer(amber, aid=1, band=ScoreLabel.AMBER)
    assert amber.score_for(RC_A).rccs < red.score_for(RC_A).rccs
    assert amber.score_for(RC_A).rccs > Decimal(0)


def test_not_applicable_produces_no_event_and_never_a_zero():
    """N/A is unscored, not a zero -- the rule ScoreLabel.is_scored enforces
    everywhere else in the pipeline."""
    assert (
        events_for_answer(
            answer_id=1,
            question_id=1,
            score_label=ScoreLabel.NOT_APPLICABLE,
            primary_root_cause_id=RC_A,
            pillar_id=PILLAR_1,
        )
        == ()
    )
    state = RCCSState()
    _answer(state, aid=1, band=ScoreLabel.NOT_APPLICABLE)
    assert state.tracked_root_cause_ids() == ()


def test_neutral_answer_does_not_inflate_an_unrelated_cause():
    state = RCCSState()
    _answer(state, aid=1, band=ScoreLabel.RED, rc=RC_A)
    assert state.score_for(RC_B).rccs == Decimal(0)


# --- 12, 13. Multi-root-cause, directional ------------------------------------

def test_12_one_answer_affects_multiple_root_causes():
    state = RCCSState()
    _answer(state, aid=1, band=ScoreLabel.RED, rc=RC_A, siblings=(RC_B, RC_C))
    assert set(state.tracked_root_cause_ids()) == {RC_A, RC_B, RC_C}


def test_13_direction_propagates_and_siblings_are_attenuated():
    """A Red raises the primary and its siblings; the siblings by less."""
    state = RCCSState()
    _answer(state, aid=1, band=ScoreLabel.RED, rc=RC_A, siblings=(RC_B,))
    assert state.score_for(RC_A).rccs > state.score_for(RC_B).rccs > Decimal(0)

    events = state.events_for(RC_B)
    assert events[0].source == "sibling"
    assert events[0].magnitude == Decimal("0.25") == SIBLING_WEIGHT
    assert events[0].direction is EvidenceDirection.SUPPORT


def test_13_one_answer_can_strengthen_and_weaken_different_causes():
    """The brief's RC-A +, RC-B +, RC-C - shape. A Green contradicts its primary
    and, through the shared problem, its siblings too."""
    state = RCCSState()
    # Two Reds establish RC_A and RC_B.
    _answer(state, aid=1, band=ScoreLabel.RED, rc=RC_A, pillar=PILLAR_1)
    _answer(state, aid=2, band=ScoreLabel.RED, rc=RC_B, pillar=PILLAR_2)
    # A Green on RC_C's question, with RC_A as a sibling.
    _answer(state, aid=3, band=ScoreLabel.GREEN, rc=RC_C, siblings=(RC_A,), pillar=PILLAR_3)

    assert state.score_for(RC_B).rccs > Decimal(0)          # untouched, positive
    assert state.score_for(RC_C).rccs == Decimal(0)          # contradicted only
    a_events = state.events_for(RC_A)
    assert [e.direction for e in a_events] == [
        EvidenceDirection.SUPPORT,
        EvidenceDirection.CONTRADICT,
    ]


def test_a_sibling_edge_alone_cannot_carry_a_cause_to_the_threshold():
    """Guards the obvious abuse of the sibling edge: implication is not evidence."""
    state = RCCSState()
    for i in range(1, 25):
        _answer(state, aid=i, band=ScoreLabel.RED, rc=RC_A, siblings=(RC_B,), pillar=i % 2)
    assert state.score_for(RC_B).rccs < RCCS_STRONG_THRESHOLD


# --- 14. Duplicate evidence ---------------------------------------------------

def test_14_replaying_the_same_answer_does_not_double_count():
    state = RCCSState()
    events = events_for_answer(
        answer_id=1, question_id=500, score_label=ScoreLabel.RED,
        primary_root_cause_id=RC_A, pillar_id=PILLAR_1,
    )
    assert state.apply_all(events) == 1
    once = state.score_for(RC_A).rccs

    assert state.apply_all(events) == 0          # rejected, and it says so
    assert state.score_for(RC_A).rccs == once


def test_14_duplicate_detection_is_per_root_cause_not_per_answer():
    """The same answer legitimately moves several causes; re-applying it moves
    none of them a second time."""
    state = RCCSState()
    events = events_for_answer(
        answer_id=1, question_id=500, score_label=ScoreLabel.RED,
        primary_root_cause_id=RC_A, sibling_root_cause_ids=(RC_B,), pillar_id=PILLAR_1,
    )
    assert state.apply_all(events) == 2
    assert state.apply_all(events) == 0


def test_rebuilding_state_from_the_trail_reproduces_the_scores():
    """The persisted event list is authoritative: replaying it is not an
    approximation of the live state, it IS the live state."""
    live = RCCSState()
    for i, band in enumerate([ScoreLabel.RED, ScoreLabel.AMBER, ScoreLabel.GREEN], start=1):
        _answer(live, aid=i, band=band, pillar=i, siblings=(RC_B,))

    rebuilt = RCCSState()
    rebuilt.apply_all(live.events)
    assert [s.rccs for s in rebuilt.all_scores()] == [s.rccs for s in live.all_scores()]


# --- 22. Evidence retention ---------------------------------------------------

def test_22_every_event_retains_the_full_trace():
    state = RCCSState()
    _answer(state, aid=77, band=ScoreLabel.RED, rc=RC_A, pillar=PILLAR_2, qid=4242)
    event = state.events_for(RC_A)[0]
    assert (event.answer_id, event.question_id, event.root_cause_id) == (77, 4242, RC_A)
    assert event.pillar_id == PILLAR_2
    assert event.score_label is ScoreLabel.RED
    assert event.direction.sign == "+"
    assert event.magnitude > 0
    assert event.source == "primary"


def test_score_exposes_the_state_that_explains_it():
    state = RCCSState()
    _answer(state, aid=1, band=ScoreLabel.RED, pillar=PILLAR_1)
    _answer(state, aid=2, band=ScoreLabel.RED, pillar=PILLAR_2)
    _answer(state, aid=3, band=ScoreLabel.GREEN, pillar=PILLAR_3)
    score = state.score_for(RC_A)
    assert score.supporting_event_count == 2
    assert score.contradicting_event_count == 1
    assert score.supporting_pillars == (PILLAR_1, PILLAR_2)
    assert score.contradicting_pillars == (PILLAR_3,)
    assert score.support_signal > score.rccs        # attenuation is visible


# --- Edge cases on the threshold ----------------------------------------------

def _to_threshold(state, rc=RC_A):
    """Drive `rc` above 0.80 the only way the model allows: two pillars."""
    _answer(state, aid=1, band=ScoreLabel.RED, rc=rc, pillar=PILLAR_1)
    _answer(state, aid=2, band=ScoreLabel.RED, rc=rc, pillar=PILLAR_1)
    _answer(state, aid=3, band=ScoreLabel.RED, rc=rc, pillar=PILLAR_2)
    return state.score_for(rc)


def test_edge_no_root_cause_reaches_the_threshold():
    state = RCCSState()
    _answer(state, aid=1, band=ScoreLabel.AMBER)
    assert state.strong_scores() == ()


def test_edge_above_threshold_qualifies():
    state = RCCSState()
    score = _to_threshold(state)
    assert score.rccs > RCCS_STRONG_THRESHOLD
    assert score.is_strong and score.has_supporting_evidence


def test_edge_exactly_at_the_threshold_qualifies():
    """>= 0.80, not > 0.80. Pinned because an off-by-one here silently changes
    the product rule."""
    from app.api.v1.diagnosis.rccs import RootCauseScore
    exact = RootCauseScore(
        root_cause_id=RC_A, rccs=Decimal("0.8000"),
        support_signal=Decimal("0.8000"), contra_signal=Decimal(0),
        supporting_pillars=(PILLAR_1,), contradicting_pillars=(),
        supporting_event_count=1, contradicting_event_count=0,
    )
    assert exact.is_strong


def test_16_threshold_without_supporting_evidence_does_not_qualify():
    """A score with nothing behind it is excluded at the source, not filtered
    downstream."""
    from app.api.v1.diagnosis.rccs import RootCauseScore
    hollow = RootCauseScore(
        root_cause_id=RC_A, rccs=Decimal("0.9000"),
        support_signal=Decimal("0.9000"), contra_signal=Decimal(0),
        supporting_pillars=(), contradicting_pillars=(),
        supporting_event_count=0, contradicting_event_count=0,
    )
    assert hollow.is_strong
    assert not hollow.has_supporting_evidence


def test_20_contradiction_can_push_a_strong_cause_back_below_the_threshold():
    """The brief's explicit requirement: 0.85 is not locked in."""
    state = RCCSState()
    assert _to_threshold(state).is_strong
    for aid, pillar in ((10, PILLAR_3), (11, 4)):
        _answer(state, aid=aid, band=ScoreLabel.GREEN, pillar=pillar)
    assert not state.score_for(RC_A).is_strong
    assert state.strong_scores() == ()


def test_21_competing_root_causes_can_change_places():
    state = RCCSState()
    _to_threshold(state, rc=RC_A)
    _answer(state, aid=20, band=ScoreLabel.RED, rc=RC_B, pillar=PILLAR_1)
    assert state.all_scores()[0].root_cause_id == RC_A

    for aid, pillar in ((30, PILLAR_2), (31, PILLAR_3)):
        _answer(state, aid=aid, band=ScoreLabel.RED, rc=RC_B, pillar=pillar)
    for aid, pillar in ((40, 5), (41, 6)):
        _answer(state, aid=aid, band=ScoreLabel.GREEN, rc=RC_A, pillar=pillar)
    assert state.all_scores()[0].root_cause_id == RC_B


def test_edge_multiple_root_causes_above_the_threshold():
    state = RCCSState()
    _to_threshold(state, rc=RC_A)
    for aid, pillar in ((10, PILLAR_1), (11, PILLAR_1), (12, PILLAR_2)):
        _answer(state, aid=aid, band=ScoreLabel.RED, rc=RC_B, pillar=pillar)
    assert {s.root_cause_id for s in state.strong_scores()} == {RC_A, RC_B}


# --- 17, 18, 19, 23, 24, 25. Quality gate and problem-driven completion --------

PROBLEM_OF = {RC_A: 1, RC_B: 1, RC_C: 2}


def _gate(state, anchors, *, pillars=True, high_value=False):
    return evaluate_quality_gate(
        state=state,
        anchor_problem_ids=frozenset(anchors),
        problem_of_root_cause=PROBLEM_OF,
        pillars_sufficient=pillars,
        high_value_question_available=high_value,
    )


def test_17_threshold_plus_evidence_plus_explanation_qualifies():
    state = RCCSState()
    _to_threshold(state, rc=RC_A)
    gate = _gate(state, {1})
    assert gate.passed
    assert [s.root_cause_id for s in gate.qualifying_causes] == [RC_A]


def test_23_gate_reports_which_check_failed():
    state = RCCSState()
    _to_threshold(state, rc=RC_A)
    assert _gate(state, {1}, pillars=False).failed_checks() == ("coverage_sufficient",)
    assert _gate(state, {1}, high_value=True).failed_checks() == ("no_high_value_question",)


def test_a_strong_cause_that_does_not_explain_the_stated_problem_fails_the_gate():
    """The anchor is the founder's problem, not whatever scored highest."""
    state = RCCSState()
    _to_threshold(state, rc=RC_C)             # problem 2
    gate = _gate(state, {1})                  # founder presented problem 1
    assert not gate.passed
    assert gate.qualifying_causes == ()
    assert gate.unexplained_problem_ids == (1,)


def test_18_first_strong_cause_does_not_end_a_partially_explained_diagnosis():
    """Two anchor problems, one explained. The gate must refuse."""
    state = RCCSState()
    _to_threshold(state, rc=RC_A)             # explains problem 1 only
    gate = _gate(state, {1, 2})
    assert not gate.passed
    assert gate.unexplained_problem_ids == (2,)

    decision = decide_completion(
        state=state, anchor_problem_ids=frozenset({1, 2}),
        problem_of_root_cause=PROBLEM_OF, pillars_sufficient=True,
        high_value_question_available=False, candidates_remaining=True,
        answered=5, safety_ceiling=100,
    )
    assert not decision.complete


def test_19_completion_fires_once_every_anchor_problem_is_explained():
    state = RCCSState()
    _to_threshold(state, rc=RC_A)             # problem 1
    for aid, pillar in ((50, PILLAR_1), (51, PILLAR_1), (52, PILLAR_2)):
        _answer(state, aid=aid, band=ScoreLabel.RED, rc=RC_C, pillar=pillar)  # problem 2

    decision = decide_completion(
        state=state, anchor_problem_ids=frozenset({1, 2}),
        problem_of_root_cause=PROBLEM_OF, pillars_sufficient=True,
        high_value_question_available=False, candidates_remaining=True,
        answered=9, safety_ceiling=100,
    )
    assert decision.complete
    assert decision.reason == PROBLEM_EXPLAINED
    assert decision.is_diagnostic_success


def test_24_a_high_value_unanswered_question_prevents_premature_completion():
    state = RCCSState()
    _to_threshold(state, rc=RC_A)
    decision = decide_completion(
        state=state, anchor_problem_ids=frozenset({1}),
        problem_of_root_cause=PROBLEM_OF, pillars_sufficient=True,
        high_value_question_available=True, candidates_remaining=True,
        answered=6, safety_ceiling=100,
    )
    assert not decision.complete


def test_edge_no_anchor_problem_means_the_diagnosis_is_not_finished():
    state = RCCSState()
    _to_threshold(state, rc=RC_A)
    assert not _gate(state, set()).passed


def test_edge_insufficient_pillar_keeps_the_diagnosis_open():
    state = RCCSState()
    _to_threshold(state, rc=RC_A)
    decision = decide_completion(
        state=state, anchor_problem_ids=frozenset({1}),
        problem_of_root_cause=PROBLEM_OF, pillars_sufficient=False,
        high_value_question_available=False, candidates_remaining=True,
        answered=6, safety_ceiling=100,
    )
    assert not decision.complete


# --- 1, 2. No fixed count; variable length ------------------------------------

def test_1_completion_is_not_a_question_count():
    """Identical evidence completes at wildly different answer counts, and an
    unexplained problem does not complete at ANY count."""
    explained = RCCSState()
    _to_threshold(explained, rc=RC_A)

    for answered in (3, 12, 30, 97):
        decision = decide_completion(
            state=explained, anchor_problem_ids=frozenset({1}),
            problem_of_root_cause=PROBLEM_OF, pillars_sufficient=True,
            high_value_question_available=False, candidates_remaining=True,
            answered=answered, safety_ceiling=250,
        )
        assert decision.complete and decision.reason == PROBLEM_EXPLAINED

    thin = RCCSState()
    _answer(thin, aid=1, band=ScoreLabel.AMBER, rc=RC_A)
    for answered in (3, 12, 30, 97):
        decision = decide_completion(
            state=thin, anchor_problem_ids=frozenset({1}),
            problem_of_root_cause=PROBLEM_OF, pillars_sufficient=True,
            high_value_question_available=False, candidates_remaining=True,
            answered=answered, safety_ceiling=250,
        )
        assert not decision.complete


def test_2_a_complex_founder_runs_longer_than_a_simple_one():
    simple = RCCSState()
    _to_threshold(simple, rc=RC_A)
    complex_ = RCCSState()
    _answer(complex_, aid=1, band=ScoreLabel.AMBER, rc=RC_A)

    def done(state, answered):
        return decide_completion(
            state=state, anchor_problem_ids=frozenset({1}),
            problem_of_root_cause=PROBLEM_OF, pillars_sufficient=True,
            high_value_question_available=False, candidates_remaining=True,
            answered=answered, safety_ceiling=250,
        ).complete

    assert done(simple, 8) and not done(complex_, 8)


def test_edge_bank_exhaustion_completes_but_is_not_a_diagnostic_success():
    state = RCCSState()
    _answer(state, aid=1, band=ScoreLabel.AMBER, rc=RC_A)
    decision = decide_completion(
        state=state, anchor_problem_ids=frozenset({1}),
        problem_of_root_cause=PROBLEM_OF, pillars_sufficient=True,
        high_value_question_available=False, candidates_remaining=False,
        answered=40, safety_ceiling=250,
    )
    assert decision.complete
    assert decision.reason == BANK_EXHAUSTED
    assert not decision.is_diagnostic_success


def test_safety_ceiling_is_last_and_is_never_a_diagnostic_success():
    """It can only catch a session that neither finished nor ran out, and it must
    never be reported as a conclusion."""
    state = RCCSState()
    _answer(state, aid=1, band=ScoreLabel.AMBER, rc=RC_A)
    decision = decide_completion(
        state=state, anchor_problem_ids=frozenset({1}),
        problem_of_root_cause=PROBLEM_OF, pillars_sufficient=True,
        high_value_question_available=False, candidates_remaining=True,
        answered=250, safety_ceiling=250,
    )
    assert decision.complete
    assert decision.reason == SAFETY_CEILING
    assert not decision.is_diagnostic_success


def test_a_finished_diagnosis_beats_the_ceiling_to_the_decision():
    """Ordering matters: a founder who is done is 'explained', never 'ceiling'."""
    state = RCCSState()
    _to_threshold(state, rc=RC_A)
    decision = decide_completion(
        state=state, anchor_problem_ids=frozenset({1}),
        problem_of_root_cause=PROBLEM_OF, pillars_sufficient=True,
        high_value_question_available=False, candidates_remaining=True,
        answered=999, safety_ceiling=30,
    )
    assert decision.reason == PROBLEM_EXPLAINED


def test_determinism_same_events_same_scores():
    def run():
        state = RCCSState()
        for i, band in enumerate(
            [ScoreLabel.RED, ScoreLabel.GREEN, ScoreLabel.AMBER, ScoreLabel.RED], start=1
        ):
            _answer(state, aid=i, band=band, pillar=i % 3, siblings=(RC_B, RC_C))
        return [(s.root_cause_id, s.rccs) for s in state.all_scores()]

    assert run() == run()
