"""Industry eligibility: the generic intersection, proved without industry-specific code.

THE ACCEPTANCE CRITERION for this step is that adding an industry's data must
not require a backend change. So the synthetic matrix here never names a real
industry in the engine's path -- it tags questions with codes and asserts the
intersection, and `test_a_brand_new_industry_works_with_no_code_change` runs the
same assertions against an industry invented inside the test.

THE CRITICAL REGRESSION is `test_wrong_industry_question_is_gone_before_ranking`:
it compares the pool BEFORE and AFTER the gate. Asserting only that the advisor
did not pick the wrong question would pass even if the question were still in the
shortlist, which is precisely the failure this architecture exists to prevent.
"""

from types import SimpleNamespace

import pytest

from app.api.v1.diagnosis.founder_context import Applicability, FounderContext
from app.api.v1.diagnosis.industry_scope import (
    filter_by_industry,
    industry_content_summary,
    is_universal,
    relevance_codes,
    verdict_for,
)

SATISFIED = Applicability.SATISFIED
CONTRADICTED = Applicability.CONTRADICTED
UNKNOWN = Applicability.UNKNOWN


def ctx(industry=None, **kw):
    founder = SimpleNamespace(
        stage=SimpleNamespace(stage_order=kw.pop("stage_order", 1), stage_name="Ideation"),
        industry_mapped=None, team_size=kw.pop("team_size", None),
        business_model=None, current_revenue=None, current_challenges=None,
    )
    return FounderContext.from_founder(founder, industry_code=industry)


def q(qid, industries, stage="Stage 0"):
    """A question double carrying only what the industry gate reads."""
    return SimpleNamespace(
        question_id=qid, industry_relevance=industries,
        primary_stage_group=stage, category="Idea & Validation",
        problem_id=1, root_cause_id=1,
    )


#: The matrix from the step brief, as data.
Q1 = q(1, ["all"])
Q2 = q(2, ["agritech"])
Q3 = q(3, ["healthtech"])
Q4 = q(4, ["agritech"], stage="Stage 1→10+")
Q5 = q(5, ["agritech", "healthtech"])
STAGE_0 = [Q1, Q2, Q3, Q5]          # Q4 is removed by the STAGE filter, upstream


def ids(questions):
    return {x.question_id for x in questions}


# --- the synthetic matrix ---------------------------------------------------
def test_agritech_founder_sees_universal_and_own_industry_only():
    result = filter_by_industry(STAGE_0, ctx("agritech"))
    assert ids(result.kept) == {1, 2, 5}
    assert result.removed_ids == {3}


def test_healthtech_founder_sees_the_mirror_image():
    result = filter_by_industry(STAGE_0, ctx("healthtech"))
    assert ids(result.kept) == {1, 3, 5}
    assert result.removed_ids == {2}


def test_unknown_industry_removes_nothing_and_marks_the_specific_ones():
    # NOT the same as ["all"]: every industry-specific question is KEPT, and
    # flagged so a later step can tell the advisor the fit is uncertain.
    result = filter_by_industry(STAGE_0, ctx(None))
    assert ids(result.kept) == {1, 2, 3, 5}
    assert result.removed_ids == frozenset()
    assert result.uncertain_ids == {2, 3, 5}
    assert 1 not in result.uncertain_ids          # universal is never uncertain


def test_a_multi_industry_question_matches_any_of_its_industries():
    for industry in ("agritech", "healthtech"):
        assert verdict_for(["agritech", "healthtech"], ctx(industry)) is SATISFIED
    assert verdict_for(["agritech", "healthtech"], ctx("saas")) is CONTRADICTED


def test_the_stage_axis_is_untouched_by_this_gate():
    # Q4 is agritech and would pass the industry gate; it is the STAGE filter's
    # job to remove it, and that runs upstream in the repository. Asserting it
    # here would give the industry gate credit for somebody else's work.
    assert verdict_for(Q4.industry_relevance, ctx("agritech")) is SATISFIED


# --- the acceptance criterion ----------------------------------------------
def test_a_brand_new_industry_works_with_no_code_change():
    # Nothing in the engine knows this code exists. If Arya seeds Beauty
    # tomorrow, this is what happens -- and it is the same code path as
    # agritech, which is the whole point.
    bank = [q(10, ["all"]), q(11, ["beauty_personal_care"]), q(12, ["agritech"])]
    result = filter_by_industry(bank, ctx("beauty_personal_care"))
    assert ids(result.kept) == {10, 11}
    assert result.removed_ids == {12}


@pytest.mark.parametrize("industry", [
    "agritech", "healthtech", "saas", "fintech", "beauty_personal_care", "gaming",
])
def test_every_industry_behaves_identically(industry):
    bank = [q(1, ["all"]), q(2, [industry]), q(3, ["some_other_industry"])]
    result = filter_by_industry(bank, ctx(industry))
    assert ids(result.kept) == {1, 2}


# --- no cross-industry fallback --------------------------------------------
def test_an_industry_with_no_content_keeps_universal_and_borrows_nothing():
    # The rule that matters when a vertical is only half seeded: a SaaS
    # retention question does not become an Agriculture question because
    # Agriculture is thin.
    bank = [q(1, ["all"]), q(2, ["all"]), q(3, ["saas"]), q(4, ["healthtech"])]
    result = filter_by_industry(bank, ctx("agritech"))
    assert ids(result.kept) == {1, 2}
    assert result.removed_ids == {3, 4}

    summary = industry_content_summary(result.kept, ctx("agritech"))
    assert summary["industry_specific_candidates"] == 0
    assert summary["industry_content_present"] is False       # a data gap, not a filter bug


def test_content_summary_distinguishes_populated_from_unpopulated():
    populated = industry_content_summary([q(1, ["all"]), q(2, ["agritech"])], ctx("agritech"))
    assert populated["industry_content_present"] is True
    assert populated["industry_specific_candidates"] == 1
    assert populated["universal_candidates"] == 1


# --- malformed metadata -----------------------------------------------------
@pytest.mark.parametrize("raw", [None, [], ["", "  "], "agritech", {"a": 1}, 42, [None]])
def test_an_unusable_relevance_value_is_treated_as_universal(raw):
    # A question nobody restricted is unrestricted. The alternative -- treating
    # a malformed row as restricted -- silently deletes questions.
    assert is_universal(raw) is True
    assert verdict_for(raw, ctx("agritech")) is SATISFIED


def test_codes_are_matched_case_insensitively_and_trimmed():
    assert verdict_for([" AgriTech "], ctx("agritech")) is SATISFIED
    assert relevance_codes([" AgriTech ", "SaaS"]) == {"agritech", "saas"}


def test_all_mixed_with_specific_codes_reads_as_universal():
    # Ambiguous data; `all` wins so the question stays askable. The mismatch is
    # reported by validate_industry_metadata rather than silently narrowed.
    assert verdict_for(["all", "agritech"], ctx("saas")) is SATISFIED


# --- the removal record -----------------------------------------------------
def test_every_removal_is_recorded_with_its_reason():
    result = filter_by_industry(STAGE_0, ctx("agritech"))
    assert result.removed == ((3, ("healthtech",)),)
    assert result.industry_code == "agritech"
    assert result.log_extra()["industry"] == "agritech"
    assert result.log_extra()["removed"] == 1


def test_the_filter_preserves_order_so_ranking_is_unperturbed():
    result = filter_by_industry(STAGE_0, ctx("agritech"))
    assert [x.question_id for x in result.kept] == [1, 2, 5]


def test_the_filter_does_not_mutate_its_input():
    before = list(STAGE_0)
    filter_by_industry(STAGE_0, ctx("agritech"))
    assert STAGE_0 == before
