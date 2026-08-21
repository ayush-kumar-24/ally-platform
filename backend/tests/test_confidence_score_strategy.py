"""Unit tests for the Overall Confidence Score strategy.

Covers CONFIDENCE_SCORE_METHODOLOGY end to end: each of the five evidence
signals, the two reliability modifiers, all six hard-rule overrides, weight
loading + the integrity check, boundary/clamping cases, and determinism. The
strategy is a pure function of its inputs and its DB-loaded constants, so these
tests need no database.
"""

from decimal import Decimal

import pytest

from app.api.v1.reasoning.config import (
    ConfidenceInputs,
    ConfidenceScoreWeights,
    ConfidenceThresholds,
)
from app.api.v1.reasoning.engines.confidence_score import ConfidenceScoreStrategy
from app.api.v1.reasoning.errors import ReasoningConfigError

D = Decimal

# The approved provisional weights from scoring_rules (sum to 1.0).
WEIGHTS = dict(
    category_signal=D("0.30"),
    coverage=D("0.25"),
    consistency=D("0.20"),
    confirmation=D("0.15"),
    separation=D("0.10"),
)


def make_strategy(**overrides) -> ConfidenceScoreStrategy:
    params = dict(
        weights=ConfidenceScoreWeights(expected_sum=D("1"), **WEIGHTS),
        stage_coherence_factor=D("1.0"),
        min_questions_floor=12,
        multi_category_flag_threshold=3,
        continue_max=D("60"),
        generate_report_min=D("80"),
    )
    params.update(overrides)
    return ConfidenceScoreStrategy(**params)


def make_inputs(**overrides) -> ConfidenceInputs:
    """Inputs that produce a perfect 100 with NO hard rule firing, so a test can
    override exactly the field under test."""
    base = dict(
        category_signal=D("1"),
        evidence_coverage=D("1"),
        consistency_available=True,
        consistency_score=D("1"),
        confirmation_ratio=D("1"),
        separation=D("1"),
        reliability_factor=D("1"),
        questions_answered=20,
        flagged_category_count=1,
        any_category_flagged=True,
        distress_override=False,
        stages_away=0,
    )
    base.update(overrides)
    return ConfidenceInputs(**base)


# --- Base formula + individual evidence signals ----------------------------


def test_all_signals_max_gives_100():
    assert make_strategy().compute(make_inputs()) == D("100")


def test_all_signals_zero_gives_0():
    inputs = make_inputs(
        category_signal=D("0"),
        evidence_coverage=D("0"),
        consistency_score=D("0"),
        confirmation_ratio=D("0"),
        separation=D("0"),
    )
    assert make_strategy().compute(inputs) == D("0")


@pytest.mark.parametrize(
    "overrides, expected",
    [
        ({"category_signal": D("1")}, D("30")),     # weight 0.30
        ({"evidence_coverage": D("1")}, D("25")),    # weight 0.25
        ({"consistency_score": D("1")}, D("20")),    # weight 0.20 (measured)
        ({"confirmation_ratio": D("1")}, D("15")),   # weight 0.15
        ({"separation": D("1")}, D("10")),           # weight 0.10
    ],
)
def test_each_signal_contributes_only_its_own_weight(overrides, expected):
    """With all five signals available, turning on one (others 0) yields exactly
    that signal's weight x100 -- proving each weight maps to the right signal and
    the denominator is 1.0 when nothing is excluded."""
    zeros = dict(
        category_signal=D("0"),
        evidence_coverage=D("0"),
        consistency_available=True,
        consistency_score=D("0"),
        confirmation_ratio=D("0"),
        separation=D("0"),
    )
    zeros.update(overrides)
    assert make_strategy().compute(make_inputs(**zeros)) == expected


def test_weighted_combination_rounds_half_up():
    # 0.30*0.5 + 0.25*0.5 = 0.275 -> *100 = 27.5 -> ROUND_HALF_UP -> 28
    inputs = make_inputs(
        category_signal=D("0.5"),
        evidence_coverage=D("0.5"),
        consistency_score=D("0"),
        confirmation_ratio=D("0"),
        separation=D("0"),
    )
    assert make_strategy().compute(inputs) == D("28")


def test_signals_are_clamped_to_unit_interval():
    # category_signal 2 -> clamped to 1 (contributes 0.30); negative -> 0.
    high = make_inputs(
        category_signal=D("2"),
        evidence_coverage=D("0"),
        consistency_score=D("0"),
        confirmation_ratio=D("0"),
        separation=D("0"),
    )
    low = make_inputs(
        category_signal=D("-5"),
        evidence_coverage=D("0"),
        consistency_score=D("0"),
        confirmation_ratio=D("0"),
        separation=D("0"),
    )
    assert make_strategy().compute(high) == D("30")
    assert make_strategy().compute(low) == D("0")


# --- Answer Consistency availability (Option B: exclude + renormalise) ------


def test_all_five_signals_available_no_renormalisation():
    # Every signal available and 1.0 -> denominator 1.0 -> plain weighted sum.
    assert make_strategy().compute(make_inputs()) == D("100")


def test_consistency_available_used_normally():
    # Four signals 1.0, consistency measured at 0.5:
    # (0.30+0.25+0.15+0.10) + 0.20*0.5 = 0.80 + 0.10 = 0.90 -> 90. No renormalise.
    inputs = make_inputs(consistency_available=True, consistency_score=D("0.5"))
    assert make_strategy().compute(inputs) == D("90")


def test_consistency_unavailable_renormalises():
    # Consistency excluded; remaining weights (0.80) renormalise to 1.0. With the
    # four available signals all 1.0 the score is a full 100 -- no confidence lost.
    inputs = make_inputs(consistency_available=False, consistency_score=None)
    assert make_strategy().compute(inputs) == D("100")


def test_consistency_unavailable_renormalises_partial():
    # Only category_signal=1, others 0, consistency excluded:
    # 0.30 / 0.80 = 0.375 -> 37.5 -> ROUND_HALF_UP -> 38.
    inputs = make_inputs(
        category_signal=D("1"),
        evidence_coverage=D("0"),
        confirmation_ratio=D("0"),
        separation=D("0"),
        consistency_available=False,
        consistency_score=None,
    )
    assert make_strategy().compute(inputs) == D("38")


def test_consistency_unavailable_is_neither_reward_nor_penalty():
    # A signal we cannot measure must not change the verdict relative to what the
    # measured signals alone say. With the four measured signals identical, the
    # excluded case equals the case where consistency happens to match their mean.
    measured_equal = make_inputs(
        category_signal=D("0.6"), evidence_coverage=D("0.6"),
        confirmation_ratio=D("0.6"), separation=D("0.6"),
        consistency_available=False, consistency_score=None,
    )
    # base = (0.80 * 0.6) / 0.80 = 0.6 -> 60
    assert make_strategy().compute(measured_equal) == D("60")


def test_consistency_available_true_but_score_none_is_excluded():
    # Guard: available=True with a None score is treated as unmeasured (excluded),
    # never as 0. Same result as the explicit unavailable case.
    inputs = make_inputs(consistency_available=True, consistency_score=None)
    assert make_strategy().compute(inputs) == D("100")


def test_weight_integrity_after_renormalisation():
    # The renormalised available weights sum to 1.0: four signals at 1.0 with
    # consistency excluded yields exactly 100 (no unit of confidence created or
    # lost by excluding the signal).
    strat = make_strategy()
    excluded = strat.compute(make_inputs(consistency_available=False, consistency_score=None))
    all_available = strat.compute(make_inputs(consistency_score=D("1")))
    assert excluded == all_available == D("100")


# --- Reliability modifiers -------------------------------------------------


@pytest.mark.parametrize("factor, expected", [(D("1.00"), D("100")), (D("0.95"), D("95")), (D("0.85"), D("85"))])
def test_session_reliability_scales_the_base(factor, expected):
    assert make_strategy().compute(make_inputs(reliability_factor=factor)) == expected


def test_unresolved_reliability_is_neutral_not_zero():
    """A missing multiplier means "we could not measure how trustworthy the
    conditions were", not "the evidence is worthless".

    Zeroing here discarded every signal that WAS measured. A real 30-answer
    session with five ranked root causes and full coverage scored 0 because one
    config lookup returned nothing, and nothing failed loudly -- the diagnosis
    just reported no confidence. High distress still discounts the score, but it
    now says so with an explicit 0 rather than by omission.
    """
    assert make_strategy().compute(make_inputs(reliability_factor=None)) > D("0")


def test_explicit_zero_reliability_still_zeroes_the_score():
    """The distress path, which genuinely does want the score discounted."""
    assert make_strategy().compute(make_inputs(reliability_factor=D("0"))) == D("0")


@pytest.mark.parametrize("coherence, expected", [(D("1.00"), D("100")), (D("0.90"), D("90")), (D("0.75"), D("75"))])
def test_stage_coherence_scales_the_base(coherence, expected):
    strat = make_strategy(stage_coherence_factor=coherence)
    assert strat.compute(make_inputs()) == expected


def test_both_modifiers_compose():
    # 1.0 base * 0.85 reliability * 0.90 coherence * 100 = 76.5 -> 77
    strat = make_strategy(stage_coherence_factor=D("0.90"))
    assert strat.compute(make_inputs(reliability_factor=D("0.85"))) == D("77")


# --- The six hard rules ----------------------------------------------------


def test_distress_no_longer_caps_the_confidence_score():
    """Distress must not rewrite the diagnostic number (product decision,
    2026-08-20).

    This asserted `== 59` while distress capped the score. Measured on a real
    session, that cap plus a 0.70 reliability discount turned an 84% evidence
    base into a reported 59, and an earlier run of the same journey showed the
    founder "0/100" on their report.

    Confidence answers "how sure are we of this diagnosis"; distress answers
    "how is this founder doing". They are independent. Distress is still
    detected, recorded on the session and routed to the support path -- it just
    no longer silently discards evidence that was gathered correctly.
    """
    got = make_strategy().compute(make_inputs(distress_override=True))
    assert got == D("100")


def test_rule2_severe_stage_mismatch_blocks_report():
    strat = make_strategy()
    assert strat.compute(make_inputs(stages_away=2)) == D("79")   # >=2 -> cap 79
    assert strat.compute(make_inputs(stages_away=3)) == D("79")
    assert strat.compute(make_inputs(stages_away=1)) == D("100")  # 1 away -> no cap
    assert strat.compute(make_inputs(stages_away=None)) == D("100")  # unknown -> no cap


def test_rule3_minimum_question_floor():
    strat = make_strategy()
    assert strat.compute(make_inputs(questions_answered=11)) == D("59")  # below floor
    assert strat.compute(make_inputs(questions_answered=12)) == D("100")  # at floor OK


def test_rule4_no_category_above_threshold_caps_to_continue():
    got = make_strategy().compute(make_inputs(any_category_flagged=False))
    assert got == D("59")


def test_rule5_multi_category_cross_check_is_advisory_not_a_cap():
    # Advisory only: many flagged categories must NOT cap the score (this cap
    # previously made generate_report unreachable). The advisory is surfaced from
    # flagged_category_count in the report, not by lowering confidence.
    strat = make_strategy()
    assert strat.compute(make_inputs(flagged_category_count=3)) == D("100")
    assert strat.compute(make_inputs(flagged_category_count=8)) == D("100")
    assert strat.compute(make_inputs(flagged_category_count=2)) == D("100")


def test_strong_session_can_reach_generate_report():
    # A clean, well-covered session with no blocking hard rule now reaches >= 80,
    # so routing can produce a report (the 0/40 gap the validation surfaced).
    from app.api.v1.reasoning.config import ConfidenceThresholds
    thresholds = ConfidenceThresholds(continue_max=D("60"), validate_min=D("60"),
                                      validate_max=D("80"), generate_report_min=D("80"))
    score = make_strategy().compute(make_inputs(flagged_category_count=5))
    assert score == D("100")
    assert thresholds.routing_state_for(score) == "generate_report"


def test_rule6_psychology_precedence_has_no_numeric_effect():
    # Rule 6 is a report-narrative ordering rule with no numeric channel; the score
    # is unaffected. There is no psychology input on ConfidenceInputs by design.
    assert make_strategy().compute(make_inputs()) == D("100")


def test_hard_rules_take_the_strongest_cap():
    # Distress no longer caps at all, so the severe-stage-mismatch cap (79) is
    # the only one applying here. Rewritten to use two rules that DO still cap
    # -- question floor (59) and stage mismatch (79) -- so this keeps testing
    # "the strongest cap wins" rather than testing the removed distress cap.
    got = make_strategy().compute(make_inputs(questions_answered=1, stages_away=2))
    assert got == D("59")

    # And distress alongside a real cap must not change the outcome.
    with_distress = make_strategy().compute(
        make_inputs(questions_answered=1, stages_away=2, distress_override=True)
    )
    assert with_distress == D("59")


def test_hard_rule_never_raises_the_score():
    # A rule can only lower: a low base with a rule firing stays low, not lifted.
    low = make_inputs(
        category_signal=D("0.1"),
        evidence_coverage=D("0"),
        consistency_score=D("0"),
        confirmation_ratio=D("0"),
        separation=D("0"),
        flagged_category_count=3,  # rule 5 cap 79
    )
    # base = 0.30*0.1*100 = 3; cap 79 does not raise it.
    assert make_strategy().compute(low) == D("3")


# --- Caps map to the existing routing thresholds ---------------------------


def test_caps_produce_expected_routing_states():
    thresholds = ConfidenceThresholds(
        continue_max=D("60"), validate_min=D("60"),
        validate_max=D("80"), generate_report_min=D("80"),
    )
    strat = make_strategy()
    # floor cap (below the question floor) -> continue. Was distress_override,
    # which no longer caps: a distressed founder keeps their real score, and the
    # support routing is decided by the pipeline, not by crushing the number.
    assert thresholds.routing_state_for(strat.compute(make_inputs(questions_answered=1))) == "continue"
    # distress alone must NOT drag routing down to continue any more
    assert thresholds.routing_state_for(
        strat.compute(make_inputs(distress_override=True))
    ) == "generate_report"
    # no-report cap (mismatch) -> validate
    assert thresholds.routing_state_for(strat.compute(make_inputs(stages_away=2))) == "validate"
    # clean 100 -> generate_report
    assert thresholds.routing_state_for(strat.compute(make_inputs())) == "generate_report"


# --- Weight loading + integrity check --------------------------------------


def test_weights_that_do_not_sum_to_one_fail_closed():
    bad = ConfidenceScoreWeights(
        category_signal=D("0.30"), coverage=D("0.25"), consistency=D("0.20"),
        confirmation=D("0.15"), separation=D("0.20"),  # sums to 1.10
        expected_sum=D("1"),
    )
    with pytest.raises(ReasoningConfigError):
        make_strategy(weights=bad)


def test_weights_within_tolerance_are_accepted():
    ok = ConfidenceScoreWeights(
        category_signal=D("0.30005"), coverage=D("0.25"), consistency=D("0.20"),
        confirmation=D("0.15"), separation=D("0.10"),  # +0.00005, within 0.0001
        expected_sum=D("1"),
    )
    make_strategy(weights=ok)  # must not raise


def test_weights_are_read_not_hardcoded():
    # A different weight distribution changes the score: category weight 1.0.
    weights = ConfidenceScoreWeights(
        category_signal=D("1"), coverage=D("0"), consistency=D("0"),
        confirmation=D("0"), separation=D("0"), expected_sum=D("1"),
    )
    strat = make_strategy(weights=weights)
    inputs = make_inputs(
        category_signal=D("0.5"), evidence_coverage=D("1"),
        consistency_available=True, consistency_score=D("1"),
        confirmation_ratio=D("1"), separation=D("1"),
    )
    assert strat.compute(inputs) == D("50")  # only category_signal counts now


# --- Boundary / clamping ---------------------------------------------------


def test_score_is_clamped_to_100():
    # A coherence factor above 1 pushes the raw score past 100; clamp holds it.
    strat = make_strategy(stage_coherence_factor=D("2"))
    assert strat.compute(make_inputs()) == D("100")


def test_score_never_negative():
    strat = make_strategy()
    got = strat.compute(make_inputs(
        category_signal=D("0"), evidence_coverage=D("0"), consistency_score=D("0"),
        confirmation_ratio=D("0"), separation=D("0"), reliability_factor=D("0"),
    ))
    assert got == D("0")


# --- Determinism -----------------------------------------------------------


def test_repeated_calls_are_identical():
    strat = make_strategy()
    inputs = make_inputs(category_signal=D("0.73"), evidence_coverage=D("0.4"))
    first = strat.compute(inputs)
    assert all(strat.compute(inputs) == first for _ in range(5))


def test_equal_inputs_give_equal_outputs():
    strat = make_strategy()
    a = make_inputs(confirmation_ratio=D("0.5"), separation=D("0.25"))
    b = make_inputs(confirmation_ratio=D("0.5"), separation=D("0.25"))
    assert strat.compute(a) == strat.compute(b)
