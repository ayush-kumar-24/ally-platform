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
from typing import get_args

import pytest
from pydantic import ValidationError

from app.schemas.founder import RETIRED_TEAM_SIZES, TeamSize
from app.schemas.sections import BusinessInfoUpdate
from app.services.profile_progress import compute_progress, validate_profile

# Spec v2.4 §2: Industry (Q6) and Audience (Q7) are Section 2 questions, asked
# in that order. They sat in Section 3 ("What Do You Know") before.
EXPECTED_SECTION = {
    "Stage": "personal",
    "Experience": "personal",
    "Monthly Revenue": "personal",
    "Team Size": "personal",
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
        team_size="2_5",
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


#: Monthly Revenue is no longer among them at Validation -- see below.
BEYOND_STAGE_0_MUST_REQUIRE = PATH_1_MUST_NOT_REQUIRE - {"Monthly Revenue"}


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
    assert BEYOND_STAGE_0_MUST_REQUIRE <= missing, (
        f"stage {stage_order} should still require "
        f"{sorted(BEYOND_STAGE_0_MUST_REQUIRE)}, missing only reports "
        f"{sorted(missing)}"
    )


# --- revenue is asked from Prototype/MVP on, not from Validation ------------
#
# Validation, Prototype/MVP and Early Traction are all Path 2 and share a
# question bank, but they are not the same business. A founder at Validation is
# testing whether anyone wants this and has no monthly revenue to report, for
# the same reason a Stage 0 founder has none. Onboarding stops asking them (the
# `minStageOrder` on the revenue part) and this stops requiring it. The two
# boundaries have to be the same number, or the profile can never be completed.

def test_validation_is_not_asked_for_monthly_revenue():
    founder = _founder(2, current_revenue=None)
    missing = {row["label"] for row in validate_profile(founder)["missing"]}
    assert "Monthly Revenue" not in missing


def test_a_validation_founder_can_finish_onboarding_without_revenue():
    """The failure this guards: requiring what is never asked makes `valid`
    permanently unreachable, which is how Path 1 broke once before."""
    assert validate_profile(_founder(2, current_revenue=None))["valid"] is True


@pytest.mark.parametrize("stage_order", [3, 4, 5, 8])
def test_prototype_onwards_is_still_asked_for_monthly_revenue(stage_order):
    founder = _founder(stage_order, current_revenue=None)
    missing = {row["label"] for row in validate_profile(founder)["missing"]}
    assert "Monthly Revenue" in missing


def test_the_onboarding_boundary_matches_the_required_boundary():
    """Read off both files rather than restated, so they cannot drift."""
    import re

    from app.core.paths import BACKEND_DIR
    from app.services.profile_progress import STAGE_ORDER_REQUIRED

    required_from = {
        column: minimum for minimum, column, _l, _s in STAGE_ORDER_REQUIRED
    }
    path = BACKEND_DIR.parent / "frontend/src/data/onboardingQuestions.js"
    if not path.exists():
        pytest.skip("frontend/ not in this checkout (backend-only build context)")
    block = re.search(
        r"field:\s*'current_revenue'.*?minStageOrder:\s*(\d+)",
        path.read_text(encoding="utf-8"), re.S,
    )
    assert block, "the revenue part lost its minStageOrder, or moved"
    assert int(block.group(1)) == required_from["current_revenue"]


# --- The diagnosis bank: an untagged question reaches nobody ----------------
#
# Not onboarding, but the same rule one phase later: every question a founder
# is asked has to be chosen for their stage. `questions.primary_stage_group`
# was nullable and NULL meant "eligible for everyone", so one question added
# without a tag would have been asked of every founder at every stage --
# silently, because nothing about it looks like an error.

class _CapturingDb:
    """Stands in for a Session just long enough to catch the built query."""

    def __init__(self):
        self.stmt = None

    def execute(self, stmt):
        self.stmt = stmt
        return self

    def scalars(self):
        return self

    def all(self):
        return []


def _candidate_sql(stage_groups):
    from app.api.v1.diagnosis.repository import DiagnosisRepository

    db = _CapturingDb()
    DiagnosisRepository(db).list_candidate_questions(
        session_id=1, stage_groups=stage_groups, founder_id=None
    )
    return str(db.stmt.compile(compile_kwargs={"literal_binds": True}))


def test_candidate_query_never_admits_an_untagged_question():
    sql = _candidate_sql(["Stage 0"])
    assert "primary_stage_group IS NULL" not in sql.replace("\n", " "), (
        "the candidate query still treats an untagged question as eligible for "
        "everyone:\n" + sql
    )


def test_candidate_query_still_filters_on_the_founders_stage_group():
    """The mirror: closing the NULL branch must not drop stage filtering
    altogether, which would serve every question to every founder instead."""
    sql = _candidate_sql(["Stage 0"]).replace("\n", " ")
    assert "primary_stage_group IN" in sql, sql
    assert "'Stage 0'" in sql, sql



# --- Team size (added 2026-09-28) -------------------------------------------
#
# founders.team_size and its six coded values shipped with the original
# schema, and nothing ever asked a founder for them, so every row held NULL.
# The diagnosis has no other way to know how many people work somewhere, so it
# put team and delegation questions to solo founders. Onboarding now asks, as a
# part of Section 1's stage question; these pin the three things that made the
# column useless before: that the API accepts it, that a wrong value is a 422
# rather than a CHECK violation, and that requiring it never becomes the reason
# an existing founder's finished profile turns incomplete.

# Read off the schema rather than hardcoded, so the merge of "26_50" and
# "50_plus" into "26_plus" (migration d71a4e8c3f05) cannot leave this asserting
# that the API still accepts a band no founder can pick.
TEAM_SIZES = list(get_args(TeamSize))


@pytest.mark.parametrize("value", TEAM_SIZES)
def test_business_update_accepts_every_team_size(value):
    assert BusinessInfoUpdate(team_size=value).team_size == value


@pytest.mark.parametrize("value", RETIRED_TEAM_SIZES)
def test_business_update_refuses_a_retired_team_size(value):
    """The column's CHECK still accepts these so a write from the old frontend
    mid-deploy does not 500. The API must not, or onboarding would keep writing
    a band nothing offers and the two would drift apart again."""
    with pytest.raises(ValidationError):
        BusinessInfoUpdate(team_size=value)


@pytest.mark.parametrize("value", ["1", "just me", "SOLO", "6-10", "100_plus"])
def test_business_update_rejects_an_unknown_team_size(value):
    """The column has a CHECK; without the Literal these reach it and come
    back as a 500 instead of telling the client what was wrong."""
    with pytest.raises(ValidationError):
        BusinessInfoUpdate(team_size=value)


def test_team_size_is_shown_in_progress_and_never_required():
    rows = {row["label"]: row for row in compute_progress(_founder(5))["fields"]}
    assert "Team Size" in rows, "onboarding asks for it but progress never lists it"
    assert rows["Team Size"]["required"] is False
    assert rows["Team Size"]["field"] == "team_size"


def test_a_profile_without_team_size_is_still_valid():
    """Every founder who onboarded before 2026-09-28 has team_size NULL.
    Requiring it would flip their profile_completed to false the next time they
    edited anything, and whatever reads the column has to handle NULL anyway."""
    assert validate_profile(_founder(5, team_size=None))["valid"] is True
