"""Onboarding conformance to `Founder DNA Onboarding — Build Spec v2.4`.

Two things are locked in here, both of which were live defects:

  * Q10 is capped at three. The schema said so in a comment and enforced
    nothing, so a request could write fifteen "biggest challenges" -- a list
    that says nothing about what a founder actually cares about most.

  * A Stage 0 founder is never held to, or shown, anything that presupposes an
    operating business. The question-level half of that already worked; the
    section assignment and the required-field split are what these tests pin.

The option-level half of the same rule lives in the frontend question set
(frontend/src/data/onboardingQuestions.js -- `activeOptions`), which has no
test runner in this repo. It is asserted there by construction: every option
that presupposes a business carries `paths: [PATH_2]`.
"""

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas.sections import BusinessInfoUpdate
from app.services.profile_progress import compute_progress, validate_profile

# Spec v2.4 §2: Industry (Q6) and Audience (Q7) are Section 2 questions, asked
# in that order. They sat in Section 3 ("What Do You Know") before.
EXPECTED_SECTION = {
    "Stage": "personal",
    "Experience": "personal",
    "Monthly Revenue": "personal",
    "Social Handle": "personal",
    "Problem": "where_you_are",
    "What you're building": "where_you_are",
    "What It Is": "where_you_are",
    "Industry": "where_you_are",
    "Who you serve": "where_you_are",
    "Founder Reality": "what_you_know",
    "Business Reality": "what_you_know",
    "Invisible Gaps": "what_you_know",
    "Biggest Challenge": "final",
    "One-Year Vision": "final",
    "90-Day Goal": "final",
}

# Everything a Stage 0 founder has no basis to answer. Each is either a whole
# question or a whole control that Path 1 must never reach.
PATH_1_MUST_NOT_REQUIRE = {"Monthly Revenue", "Business Reality", "What It Is", "One-Year Vision"}


def _founder(stage_order, **overrides):
    """A founder with every required onboarding field filled."""
    base = dict(
        founder_id=1,
        stage_id=2,
        profile_completed=True,
        experience_level="one_company",
        problem_statement="Churn is high.",
        building_summary="Compliance SaaS.",
        product_description="Plant data in, compliance reports out.",
        customer_segment=["mid-size manufacturers"],
        industry="SaaS",
        current_revenue="1L_5L",
        founder_reality_signals={"decisive": True},
        business_reality_signals={"revenue_predictable": False},
        invisible_gaps=["No clear roadmap"],
        current_challenges=["Sales"],
        goal_90_day="Cut churn to 3%",
        vision_1_year="Rs 4Cr ARR",
        linkedin_url=None,
        stage=SimpleNamespace(stage_order=stage_order, question_budget=None),
    )
    base.update(overrides)
    return SimpleNamespace(**base)


# --- Q10: "Pick up to three" ------------------------------------------------

def test_biggest_challenge_accepts_three():
    update = BusinessInfoUpdate(current_challenges=["Sales", "Marketing", "Hiring"])
    assert update.current_challenges == ["Sales", "Marketing", "Hiring"]


@pytest.mark.parametrize("count", [4, 5, 15])
def test_biggest_challenge_rejects_more_than_three(count):
    """The control bumps the oldest pick, so a founder never sends a 4th --
    this bounds a hand-rolled request, which is the only way one arrives."""
    picks = [f"Challenge {n}" for n in range(count)]
    with pytest.raises(ValidationError):
        BusinessInfoUpdate(current_challenges=picks)


# --- Section assignment -----------------------------------------------------

@pytest.mark.parametrize("stage_order", [1, 2, 5, 8])
def test_every_progress_field_sits_in_its_spec_section(stage_order):
    rows = compute_progress(_founder(stage_order))["fields"]
    assert rows, "progress returned no fields at all"
    for row in rows:
        expected = EXPECTED_SECTION.get(row["label"])
        assert expected is not None, f"unmapped progress field {row['label']!r}"
        assert row["section"] == expected, (
            f"{row['label']!r} is in {row['section']!r}, spec v2.4 puts it in {expected!r}"
        )


# --- Stage 0 is never asked about a business it does not have ---------------

def test_stage_0_is_never_required_to_answer_business_questions():
    labels = {row["label"] for row in compute_progress(_founder(1))["fields"] if row["required"]}
    leaked = labels & PATH_1_MUST_NOT_REQUIRE
    assert not leaked, f"Stage 0 founder required to answer {sorted(leaked)}"


def test_stage_0_profile_is_complete_without_revenue_or_business_reality():
    """The whole point of Path 1: a founder with only an idea can finish
    onboarding. Requiring any of these would make that impossible, which is
    how `valid` became permanently unreachable once before."""
    founder = _founder(
        1,
        current_revenue=None,
        business_reality_signals=None,
        product_description=None,
        vision_1_year=None,
    )
    result = validate_profile(founder)
    assert result["valid"], result["missing"]


@pytest.mark.parametrize("stage_order", [2, 5, 8])
def test_beyond_stage_0_still_requires_the_business_questions(stage_order):
    """The mirror of the test above -- path filtering has to narrow Path 1
    without quietly dropping the requirement for everyone else."""
    founder = _founder(
        stage_order,
        current_revenue=None,
        business_reality_signals=None,
        product_description=None,
        vision_1_year=None,
    )
    missing = {row["label"] for row in validate_profile(founder)["missing"]}
    assert PATH_1_MUST_NOT_REQUIRE <= missing, (
        f"stage {stage_order} should still require {sorted(PATH_1_MUST_NOT_REQUIRE)}, "
        f"missing only reports {sorted(missing)}"
    )
