"""The stage prior: a four-level relevance scale, not a probability.

`root_cause_weights.stage_weight` carries 0.5 / 1.0 / 1.5 / 2.0 -- low,
moderate, high and peak relevance at a given founder stage -- and a CHECK
constraint on the column allows nothing else.

It was read with `_clamp(w, 0, 1)`, which is correct for a probability and
wrong for a relevance scale. Counted on the shipped catalogue (9,776 rows in
15_root_cause_weights.sql):

    0.50  x 1,000   ->  0.50
    1.00  x 2,062   ->  1.00
    1.50  x 3,674   ->  1.00   collapsed
    2.00  x 3,040   ->  1.00   collapsed

6,714 rows -- 69% of the catalogue -- lost the distinction the column exists to
record. A factor carrying 20% of the ranking stopped separating the causes it
was meant to separate, and the resulting ties fall through to the deterministic
tie-break, which is root_cause_id. Which finding reached a founder's top three
could turn on a surrogate key.

Normalising rather than un-clamping is the other half of the fix, and the tests
here spend as much effort on the ceiling as on the spread: letting 2.0 through
raw would give a 0.20-weighted factor a 0.40 contribution, equal to category
risk -- the factor the scoring document calls the highest weighted and to which
stage is explicitly "subordinate".
"""

from decimal import Decimal

import pytest

from app.api.v1.reasoning.engines.confidence import (
    _STAGE_WEIGHT_MAX,
    _STAGE_WEIGHT_MIN,
    normalise_stage_weight,
)

#: The only four values the CHECK constraint permits.
LOW, MODERATE, HIGH, PEAK = (
    Decimal("0.5"), Decimal("1.0"), Decimal("1.5"), Decimal("2.0"))

#: WEIGHT_STAGE_PROBABILITY from scoring_rules.
STAGE_WEIGHT = Decimal("0.20")


# --- the bug -------------------------------------------------------------


def test_all_four_levels_stay_distinct():
    """The whole point. Under the clamp the top three were one value."""
    values = [normalise_stage_weight(w) for w in (LOW, MODERATE, HIGH, PEAK)]
    assert len(set(values)) == 4, values


def test_the_levels_stay_in_order():
    assert (normalise_stage_weight(LOW)
            < normalise_stage_weight(MODERATE)
            < normalise_stage_weight(HIGH)
            < normalise_stage_weight(PEAK))


def test_peak_and_moderate_no_longer_contribute_the_same():
    """Stated as the ranking contribution, because that is where it was lost:
    both were 1.0 x 0.20 = 0.20 before."""
    assert (normalise_stage_weight(PEAK) * STAGE_WEIGHT
            != normalise_stage_weight(MODERATE) * STAGE_WEIGHT)


def test_high_and_peak_no_longer_contribute_the_same():
    """The two most common values in the catalogue -- 3,674 and 3,040 rows --
    and the pair whose collapse cost the most."""
    assert (normalise_stage_weight(HIGH) != normalise_stage_weight(PEAK))


# --- the ceiling ---------------------------------------------------------


def test_the_factor_never_exceeds_its_configured_weight():
    """Un-clamping instead of normalising would have made stage a 0.40 factor,
    equal to category risk. The scoring document calls stage subordinate to it,
    so the ceiling is as load-bearing as the spread."""
    for w in (LOW, MODERATE, HIGH, PEAK):
        assert normalise_stage_weight(w) * STAGE_WEIGHT <= STAGE_WEIGHT


def test_peak_relevance_scores_exactly_the_full_weight():
    assert normalise_stage_weight(PEAK) == 1
    assert normalise_stage_weight(PEAK) * STAGE_WEIGHT == STAGE_WEIGHT


def test_a_weight_above_the_constrained_range_cannot_break_the_ceiling():
    """Impossible under the CHECK constraint today; this function is also the
    contract for whatever edits the column next."""
    assert normalise_stage_weight(Decimal("99")) == 1


def test_a_weight_below_the_range_cannot_go_negative():
    """A negative contribution would subtract from a root cause's score, which
    no reading of a relevance scale supports."""
    assert normalise_stage_weight(Decimal("-5")) == 0


# --- the scale itself ----------------------------------------------------


@pytest.mark.parametrize("weight,expected", [
    (LOW, "0.00"), (MODERATE, "0.33"), (HIGH, "0.67"), (PEAK, "1.00"),
])
def test_the_shipped_mapping(weight, expected):
    assert abs(normalise_stage_weight(weight) - Decimal(expected)) <= Decimal("0.005")


def test_relative_differences_are_preserved():
    """Min-max is linear, so the four levels stay evenly spaced -- the gap
    between low and moderate equals the gap between high and peak, exactly as
    the source scale has them."""
    low, moderate, high, peak = (
        normalise_stage_weight(w) for w in (LOW, MODERATE, HIGH, PEAK))
    step = peak - high
    assert abs((moderate - low) - step) <= Decimal("0.005")
    assert abs((high - moderate) - step) <= Decimal("0.005")


def test_a_missing_weight_contributes_nothing():
    assert normalise_stage_weight(None) == 0


def test_low_relevance_and_no_weight_share_a_contribution():
    """The documented trade-off of a min-max scale, asserted rather than left
    implicit: the bottom of a scale is its zero, so 'low relevance here' and
    'no weight row at all' rank alike. They stay distinguishable downstream --
    ScoreComponent.available records which is which -- and switching to
    weight / _STAGE_WEIGHT_MAX would separate them at the cost of no level ever
    scoring zero. If that trade is ever revisited, this test is the one to
    change."""
    assert normalise_stage_weight(LOW) == normalise_stage_weight(None)


def test_the_bounds_match_the_database_check_constraint():
    """root_cause_weights_stage_weight_check allows exactly
    ARRAY[0.5, 1.0, 1.5, 2.0], so these two constants are its endpoints. A
    migration widening the column must change them together."""
    assert _STAGE_WEIGHT_MIN == LOW
    assert _STAGE_WEIGHT_MAX == PEAK
