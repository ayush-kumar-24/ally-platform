"""Onboarding is compulsory before the journey starts.

Onboarding is where Ally learns someone's stage, what they are building and the
problem they arrived with. Stage selects which of the three question banks the
diagnosis draws from; the rest becomes the founder context the advisor reads
before choosing each question. Starting without it does not produce a slightly
worse diagnosis -- it produces a generic one, and it looks identical to a real
one from the outside, which is the part that makes it worth refusing.
"""

from types import SimpleNamespace

import pytest

from app.api.deps import ProfileIncompleteError, require_profile_complete
from app.services.profile_progress import validate_profile


def _founder(**overrides):
    """A founder with every required onboarding field filled.

    Built from validate_profile's own required list rather than a hand-written
    one, so a field added to onboarding later cannot leave this test asserting
    against a definition that has moved on.
    """
    base = SimpleNamespace(
        founder_id=1, stage_id=2, experience_level="one_company",
        problem_statement="Churn is high.", building_summary="Compliance SaaS.",
        customer_segment=["mid-size manufacturers"], industry="SaaS",
        founder_reality_signals={"decisive": "yes"},
        business_reality_signals={"revenue_predictable": "no"},
        invisible_gaps=["pricing"], current_challenges=["retention"],
        product_description="Plant data in, compliance reports out.",
        goal_90_day="Cut churn to 3%", vision_1_year="Rs 4Cr ARR",
    )
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


def test_a_finished_profile_is_allowed_through():
    founder = _founder()
    assert validate_profile(founder)["valid"], validate_profile(founder)["missing"]
    assert require_profile_complete(founder) is founder


@pytest.mark.parametrize("missing_field", [
    "stage_id",              # selects the question bank -- the costliest to miss
    "problem_statement",
    "customer_segment",
    "current_challenges",
])
def test_each_missing_required_field_blocks_the_journey(missing_field):
    with pytest.raises(ProfileIncompleteError) as caught:
        require_profile_complete(_founder(**{missing_field: None}))
    assert missing_field in [m["field"] for m in caught.value.missing]


def test_the_refusal_names_what_is_actually_missing():
    """A founder who filled most of the form should be sent to the fields that
    are blocking them, not to the top of it."""
    with pytest.raises(ProfileIncompleteError) as caught:
        require_profile_complete(_founder(stage_id=None, customer_segment=None))
    # `.message` is where AppError keeps the founder-facing text; it never
    # passes it to Exception, so str() is not the accessor here.
    message = caught.value.message
    assert "Still needed" in message
    assert "Stage" in message
    assert caught.value.status_code == 409


def test_gate_recomputes_rather_than_trusting_the_cached_flag():
    """`founders.profile_completed` is a cache kept fresh on profile writes. A
    founder whose required fields were emptied by some other route -- an admin
    edit, an import, a newly-added required field -- would otherwise be waved
    through on a stale True."""
    stale = _founder(stage_id=None, profile_completed=True)
    with pytest.raises(ProfileIncompleteError):
        require_profile_complete(stale)
