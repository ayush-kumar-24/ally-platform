"""CONFIDENCE_UNAVAILABLE_INPUT_HANDLING, applied to all five signals.

The rule is explicit: a signal that could not be measured is EXCLUDED and the
remaining weights renormalise to 1.0. It is "never defaulted to 1.0 and never
defaulted to 0", and it "applies to all five inputs, not only Answer
Consistency".

Only consistency was gated. Confirmation and separation were always included, so
a session with no ranked root cause scored both 0 -- the forbidden case. Nothing
had been checked and found clean; there had been nothing to check. That charged a
founder with no detected problem 25% of their score for not having one.

The rule also carries a floor, which was not implemented at all: at least three
of the five must be measurable, or the score is capped and routing stays on
`continue`. Renormalising onto one signal produces a number that looks like a
confidence measure without being one.
"""

from decimal import Decimal

import pytest

from app.api.v1.reasoning.config import ConfidenceInputs, ConfidenceScoreWeights
from app.api.v1.reasoning.engines.confidence_score import ConfidenceScoreStrategy

D = Decimal

# Live scoring_rules values.
WEIGHTS = ConfidenceScoreWeights(
    category_signal=D("0.30"), coverage=D("0.25"), consistency=D("0.20"),
    confirmation=D("0.15"), separation=D("0.10"),
)
CONTINUE_MAX = D("60")
REPORT_MIN = D("80")
FLOOR_CAP = CONTINUE_MAX - 1     # 59 -- keeps routing on `continue`


def _strategy(min_measurable=3):
    return ConfidenceScoreStrategy(
        weights=WEIGHTS, stage_coherence_factor=D("1.0"), min_questions_floor=12,
        multi_category_flag_threshold=3, continue_max=CONTINUE_MAX,
        generate_report_min=REPORT_MIN, min_measurable_inputs=min_measurable,
    )


def _inputs(**kw):
    base = dict(
        category_signal=D("0"), evidence_coverage=D("1.0"),
        confirmation_ratio=D("0"), separation=D("0"),
        consistency_available=True, consistency_score=D("1.0"),
        reliability_factor=D("1.0"), questions_answered=30,
        flagged_category_count=0, any_category_flagged=False,
        distress_override=False, stages_away=0,
    )
    base.update(kw)
    return ConfidenceInputs(**base)


# A base with a flagged category, used wherever a test needs to observe the
# renormalisation itself. Hard rule 4 caps any UNFLAGGED session at 59 whatever
# the arithmetic says, which would otherwise mask the difference these tests are
# measuring. The realistic healthy-founder case is tested separately below.
def _flagged(**kw):
    base = dict(category_signal=D("0.5"), flagged_category_count=2,
                any_category_flagged=True)
    base.update(kw)
    return _inputs(**base)


# --- the bug: unmeasurable signals were scored zero -----------------------

def test_excluding_unmeasurable_signals_renormalises_the_rest():
    """0.30 + 0.25 + 0.20 = 0.75 of weight was measured, so it is divided by 0.75
    rather than averaged against two zeroes nobody measured."""
    s = _strategy()
    excluded = s.compute(_flagged(confirmation_available=False, separation_available=False))
    scored_zero = s.compute(_flagged())      # flags default True, the old behaviour

    assert excluded == 80
    assert scored_zero == 60


def test_a_healthy_founder_is_not_charged_for_having_no_root_cause():
    """The realistic case, end to end. With no detected cause, confirmation and
    separation cannot be measured; excluding them lifts the honest score from 45
    to 60. Hard rule 4 then caps an unflagged session at 59, which is exactly why
    the monitor route exists -- but the reported number is no longer understating
    the evidence by fifteen points."""
    s = _strategy()
    fixed = s.compute(_inputs(confirmation_available=False, separation_available=False))
    old = s.compute(_inputs())

    assert old == 45
    assert fixed == 59


def test_an_unmeasured_signal_is_never_given_a_free_1_0():
    """The other half of the rule. Excluding must not become rewarding: a founder
    whose measured evidence is genuinely weak stays low."""
    score = _strategy().compute(_flagged(
        category_signal=D("0.1"), evidence_coverage=D("0.2"), consistency_score=D("0.3"),
        confirmation_available=False, separation_available=False))
    assert score < CONTINUE_MAX


def test_a_measured_zero_still_counts_as_evidence():
    """State 2 in the rule: a signal that ran and found nothing is a real
    measurement. Two causes that are perfectly tied genuinely separate at 0, and
    that must keep dragging the score down rather than dropping out."""
    s = _strategy()
    tied = s.compute(_flagged(separation=D("0"), separation_available=True,
                              confirmation_ratio=D("1.0")))
    unmeasured = s.compute(_flagged(separation_available=False,
                                    confirmation_ratio=D("1.0")))
    assert tied == 75
    assert unmeasured == 83
    assert tied < unmeasured


def test_category_signal_can_also_be_excluded():
    """The rule covers all five. No classified answer means the strongest-risk
    figure is a max() over nothing, not a reading of zero risk."""
    s = _strategy()
    excluded = s.compute(_flagged(category_signal=D("0"), category_signal_available=False))
    included = s.compute(_flagged(category_signal=D("0"), category_signal_available=True))
    assert excluded > included


def test_coverage_is_always_counted():
    """Answered-over-budget is always computable, so it has no availability flag
    and must never drop out of the sum."""
    score = _strategy().compute(_flagged(
        evidence_coverage=D("0"), consistency_available=False,
        confirmation_available=False, separation_available=False))
    assert score is not None


# --- the missing guard ----------------------------------------------------

def test_too_few_measured_signals_caps_the_score():
    """Renormalising onto one signal is not a confidence measure. Below the floor
    the score is capped so the diagnosis keeps gathering."""
    score = _strategy(min_measurable=3).compute(_flagged(
        evidence_coverage=D("1.0"), consistency_available=False,
        confirmation_available=False, separation_available=False,
        category_signal_available=False))          # only coverage measured
    assert score <= FLOOR_CAP


def test_the_capped_score_keeps_routing_on_continue():
    score = _strategy(min_measurable=3).compute(_flagged(
        consistency_available=False, confirmation_available=False,
        separation_available=False, category_signal_available=False))
    assert score < CONTINUE_MAX
    assert score < REPORT_MIN


def test_three_measured_signals_is_enough():
    """Three is the documented minimum, so a three-signal session is scored
    normally rather than capped."""
    score = _strategy(min_measurable=3).compute(
        _flagged(confirmation_available=False, separation_available=False))
    assert score == 80


@pytest.mark.parametrize("floor,expected_capped", [(3, False), (4, True), (5, True)])
def test_the_floor_comes_from_configuration(floor, expected_capped):
    """The rule_value is the authority, not a literal in the strategy."""
    three_measured = _flagged(confirmation_available=False, separation_available=False)
    score = _strategy(min_measurable=floor).compute(three_measured)
    assert (score <= FLOOR_CAP) is expected_capped


def test_a_full_five_signal_session_is_untouched():
    """The regression guard: nothing about a complete session changes."""
    score = _strategy().compute(_inputs(
        category_signal=D("1.0"), confirmation_ratio=D("1.0"),
        separation=D("0.90"), flagged_category_count=5, any_category_flagged=True))
    assert score == 99
