"""The confirmation factor: one reading of the multiplier, not two.

`scoring_rules` defines CONFIRMED 1.5, UNCONFIRMED 1.0, NOT_TESTED 0.5 and
calls the factor "25%". Two models in `confidence.py` read that number, and
until now they disagreed:

    ranking      raw x 0.25   ->  0.125 / 0.250 / 0.375
    confidence   normalised   ->  0.000 / 0.500 / 1.000

The ranking reading made the factor a 37.5% one and pushed the maximum
attainable score to 0.40 + 0.375 + 0.20 + 0 + 0.15 = 1.125.
WEIGHT_FACTORS_SUM_CHECK does not catch it: it asserts the five WEIGHTS sum to
1.0, never the score they can produce. And the score is founder-facing --
`reporting/generator.py` passes `final_weighted_score` into
`RootCauseHighlight.confidence` -- so a confirmed cause in a strong category
could report a confidence above 1.

The tests below are in two halves, and the second half is the one that made
this change safe to make: the transform is linear and identical for every root
cause, so no ranking can move.
"""

from decimal import Decimal

import pytest

from app.api.v1.reasoning.config import ConfirmationMultipliers
from app.api.v1.reasoning.engines.confidence import normalise_confirmation

#: The seeded values, from 04_scoring_rules.sql.
MULTIPLIERS = ConfirmationMultipliers(
    confirmed=Decimal("1.5"),
    unconfirmed=Decimal("1.0"),
    not_tested=Decimal("0.5"),
)

#: WEIGHT_CONFIRMATION_STATUS.
CONFIRMATION_WEIGHT = Decimal("0.25")

#: The other four ranking weights, so the ceiling can be asserted against the
#: real formula rather than against this factor in isolation.
CATEGORY_RISK_WEIGHT = Decimal("0.40")
STAGE_WEIGHT = Decimal("0.20")
INDUSTRY_WEIGHT = Decimal("0.00")          # moved to evidence breadth
BREADTH_WEIGHT = Decimal("0.15")


# --- the scale -----------------------------------------------------------


def test_the_three_statuses_map_onto_zero_half_one():
    assert normalise_confirmation(Decimal("0.5"), MULTIPLIERS) == 0
    assert normalise_confirmation(Decimal("1.0"), MULTIPLIERS) == Decimal("0.5")
    assert normalise_confirmation(Decimal("1.5"), MULTIPLIERS) == 1


def test_confirmation_is_now_worth_exactly_its_configured_weight():
    """25% means 25%. It reached 37.5% before."""
    best = normalise_confirmation(MULTIPLIERS.confirmed, MULTIPLIERS)
    assert best * CONFIRMATION_WEIGHT == CONFIRMATION_WEIGHT


def test_the_maximum_attainable_score_is_now_one():
    """The whole formula, at its ceiling. 1.125 before."""
    ceiling = (
        CATEGORY_RISK_WEIGHT * 1
        + CONFIRMATION_WEIGHT * normalise_confirmation(
            MULTIPLIERS.confirmed, MULTIPLIERS)
        + STAGE_WEIGHT * 1
        + INDUSTRY_WEIGHT * 1
        + BREADTH_WEIGHT * 1
    )
    assert ceiling == 1


def test_a_founder_facing_confidence_can_no_longer_exceed_one():
    """`final_weighted_score` is passed straight into
    RootCauseHighlight.confidence by reporting/generator.py."""
    worst_case = CATEGORY_RISK_WEIGHT + CONFIRMATION_WEIGHT * normalise_confirmation(
        MULTIPLIERS.confirmed, MULTIPLIERS) + STAGE_WEIGHT + BREADTH_WEIGHT
    assert worst_case <= 1


# --- why this cannot reorder anything ------------------------------------


def test_the_gaps_between_statuses_are_unchanged():
    """The transform is (m - 0.5) / 1.0 -- a linear shift. Each step was 0.125
    of the final score before and is 0.125 now, so no pair of causes separated
    by confirmation alone can swap."""
    before = {
        "not_tested": Decimal("0.5") * CONFIRMATION_WEIGHT,
        "unconfirmed": Decimal("1.0") * CONFIRMATION_WEIGHT,
        "confirmed": Decimal("1.5") * CONFIRMATION_WEIGHT,
    }
    after = {
        name: normalise_confirmation(Decimal(raw), MULTIPLIERS) * CONFIRMATION_WEIGHT
        for name, raw in (("not_tested", "0.5"), ("unconfirmed", "1.0"),
                          ("confirmed", "1.5"))
    }
    assert (before["unconfirmed"] - before["not_tested"]
            == after["unconfirmed"] - after["not_tested"])
    assert (before["confirmed"] - before["unconfirmed"]
            == after["confirmed"] - after["unconfirmed"])


def test_every_status_shifts_by_the_same_amount():
    """The definition of ranking-neutral: one constant subtracted from every
    root cause in a session."""
    shifts = {
        (Decimal(raw) * CONFIRMATION_WEIGHT)
        - (normalise_confirmation(Decimal(raw), MULTIPLIERS) * CONFIRMATION_WEIGHT)
        for raw in ("0.5", "1.0", "1.5")
    }
    assert len(shifts) == 1
    assert shifts.pop() == Decimal("0.125")


def test_the_status_order_is_preserved():
    assert (normalise_confirmation(Decimal("0.5"), MULTIPLIERS)
            < normalise_confirmation(Decimal("1.0"), MULTIPLIERS)
            < normalise_confirmation(Decimal("1.5"), MULTIPLIERS))


# --- degrade paths -------------------------------------------------------


@pytest.mark.parametrize("confirmed,not_tested", [
    ("0.5", "0.5"),        # zero span
    ("0.5", "1.5"),        # inverted
])
def test_misconfigured_multipliers_report_unavailable_not_zero(confirmed, not_tested):
    """None, never 0. A clean zero would claim the factor was measured and
    found absent; the caller records it unavailable instead, the same reading
    every other factor gives to 'we could not compute this'. Falling back to
    the raw multiplier would quietly restore the >1 score."""
    broken = ConfirmationMultipliers(
        confirmed=Decimal(confirmed),
        unconfirmed=Decimal("1.0"),
        not_tested=Decimal(not_tested),
    )
    assert normalise_confirmation(Decimal("1.5"), broken) is None


def test_a_multiplier_outside_the_configured_range_cannot_break_the_ceiling():
    assert normalise_confirmation(Decimal("99"), MULTIPLIERS) == 1
    assert normalise_confirmation(Decimal("-5"), MULTIPLIERS) == 0


def test_retuned_multipliers_still_normalise_to_the_same_ceiling():
    """The rescaling reads the configured multipliers, so calibration changing
    them in scoring_rules cannot reintroduce a factor worth more than its
    weight."""
    retuned = ConfirmationMultipliers(
        confirmed=Decimal("3.0"), unconfirmed=Decimal("2.0"),
        not_tested=Decimal("1.0"),
    )
    assert normalise_confirmation(Decimal("3.0"), retuned) == 1
    assert normalise_confirmation(Decimal("1.0"), retuned) == 0
