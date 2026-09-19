"""Step 4: three-valued applicability, the pool floor, and N/A as a real state.

THE ONE RULE THIS FILE EXISTS TO PROTECT is that UNKNOWN is not NO. Every gate
before this one could only ever remove a question on positive evidence; this is
the first that reads a precondition attached to CONTENT, so it is the first that
could silently delete questions from founders whose onboarding is incomplete --
which is most of them. The unknown-side tests here are therefore not symmetry
for its own sake: they are the failure mode.

Synthetic preconditions throughout. The engine is data-driven, so a test that
depended on the three curated `hr-*` tags would prove the curation rather than
the mechanism, and would skip on any database that had not run b7c2d94e5f10.
The live curation is asserted separately, in test_tag_preconditions.py.
"""

from types import SimpleNamespace

import pytest

from app.api.v1.diagnosis.applicability import (
    NEVER_RELAXED,
    RELAXATION_LADDER,
    ApplicabilityResult,
    filter_by_applicability,
    relax_to_floor,
    verdict_for_tokens,
)
from app.api.v1.diagnosis.founder_context import (
    Applicability,
    FounderContext,
    TOKEN_HAS_TEAM,
)

SATISFIED = Applicability.SATISFIED
CONTRADICTED = Applicability.CONTRADICTED
UNKNOWN = Applicability.UNKNOWN


def ctx(**kw):
    """A FounderContext from a founder double. Absent kwarg == field not set."""
    founder = SimpleNamespace(
        stage=SimpleNamespace(stage_order=kw.pop("stage_order", 5), stage_name="Growth"),
        industry_mapped=None,
        team_size=kw.pop("team_size", None),
        business_model=kw.pop("business_model", None),
        current_revenue=kw.pop("current_revenue", None),
        current_challenges=kw.pop("current_challenges", None),
    )
    return FounderContext.from_founder(founder, industry_code=kw.pop("industry", None))


def q(qid):
    return SimpleNamespace(question_id=qid, category="Team & Leadership",
                           problem_id=1, root_cause_id=1, industry_relevance=["all"])


# =========================================================== A / B: three values
def test_solo_founder_contradicts_a_team_dependent_question():
    """Case 1. The whole point: `solo` is a POSITIVE statement of no team."""
    assert ctx(team_size="solo").verdict(TOKEN_HAS_TEAM) is CONTRADICTED
    result = filter_by_applicability([q(1)], ctx(team_size="solo"),
                                     {1: frozenset({TOKEN_HAS_TEAM})})
    assert result.removed_ids == {1}
    assert result.kept == ()


def test_unknown_team_size_keeps_the_same_question():
    """Case 2. The failure mode. A founder who never told us is NOT solo."""
    context = ctx(team_size=None)
    assert context.verdict(TOKEN_HAS_TEAM) is UNKNOWN
    result = filter_by_applicability([q(1)], context, {1: frozenset({TOKEN_HAS_TEAM})})
    assert result.removed_ids == frozenset()
    assert result.uncertain_ids == {1}          # kept, and flagged as an uncertain fit


def test_a_founder_with_a_team_satisfies_it():
    context = ctx(team_size="6_10")
    assert context.verdict(TOKEN_HAS_TEAM) is SATISFIED
    result = filter_by_applicability([q(1)], context, {1: frozenset({TOKEN_HAS_TEAM})})
    assert result.kept == (result.kept[0],)
    assert result.uncertain_ids == frozenset()  # certain, so never marked uncertain


@pytest.mark.parametrize("team_size", ["2_5", "6_10", "11_25", "26_50", "50_plus"])
def test_every_non_solo_bucket_satisfies_has_team(team_size):
    assert ctx(team_size=team_size).verdict(TOKEN_HAS_TEAM) is SATISFIED


# =========================================================== C: the other axes
def test_a_known_business_model_contradicts_another_one():
    """Case 3, through the generic family machinery rather than a special case."""
    context = ctx(business_model="B2B")
    assert context.verdict("model:b2c") is CONTRADICTED
    assert context.verdict("model:b2b") is SATISFIED
    result = filter_by_applicability([q(1)], context, {1: frozenset({"model:b2c"})})
    assert result.removed_ids == {1}


def test_an_unknown_business_model_keeps_the_question():
    """Case 4."""
    context = ctx(business_model=None)
    assert context.verdict("model:b2c") is UNKNOWN
    result = filter_by_applicability([q(1)], context, {1: frozenset({"model:b2c"})})
    assert result.kept and result.uncertain_ids == {1}


def test_a_known_industry_contradicts_another_one():
    """Case 5, at the token level -- questions.industry_relevance is Step 3's."""
    assert ctx(industry="agritech").verdict("industry:fintech") is CONTRADICTED


def test_an_unknown_industry_keeps_the_question():
    """Case 6."""
    assert ctx(industry=None).verdict("industry:fintech") is UNKNOWN


def test_solo_does_not_contradict_founder_dependency_tokens():
    """The rule the curation is built on: solo is not "no founder problems".

    A solo founder is the founder MOST likely to have delegation-readiness,
    workload and bottleneck problems. Nothing about `team_size='solo'` may
    contradict a token that is about the FOUNDER rather than about employees.
    """
    context = ctx(team_size="solo")
    for token in ("stage:5", "has_revenue", "model:b2b", "challenge:growth"):
        assert context.verdict(token) is not CONTRADICTED, token


# =========================================================== conjunction rules
def test_one_contradiction_removes_however_many_tokens_are_satisfied():
    context = ctx(team_size="solo", business_model="B2B")
    assert verdict_for_tokens({TOKEN_HAS_TEAM, "model:b2b"}, context) is CONTRADICTED


def test_contradiction_beats_unknown_regardless_of_token_order():
    context = ctx(team_size="solo", business_model=None)
    for tokens in ([TOKEN_HAS_TEAM, "model:b2c"], ["model:b2c", TOKEN_HAS_TEAM]):
        assert verdict_for_tokens(tokens, context) is CONTRADICTED


def test_an_untagged_question_is_unconditional():
    # 3,369 of 3,460 questions rely on this.
    assert verdict_for_tokens(None, ctx(team_size="solo")) is SATISFIED
    assert verdict_for_tokens(frozenset(), ctx(team_size="solo")) is SATISFIED
    result = filter_by_applicability([q(1), q(2)], ctx(team_size="solo"), {})
    assert len(result.kept) == 2


def test_an_unrecognised_token_is_unknown_never_contradicted():
    # A curation typo must not silently delete questions.
    assert ctx(team_size="solo").verdict("has_tema") is UNKNOWN


# =========================================================== F: the pool floor
def _pool(n):
    return [q(i) for i in range(n)]


def test_a_full_pool_relaxes_nothing():
    outcome = relax_to_floor(_pool(9), [("industry_scope", _pool(20))], 5)
    assert outcome.relaxed == ()
    assert len(outcome.candidates) == 9
    assert outcome.floor_unreached is False


def test_a_short_pool_climbs_one_rung_and_says_so():
    """Case 13. Relaxation is explicit, ordered, observable and logged."""
    outcome = relax_to_floor(_pool(2), [("industry_scope", _pool(7))], 5)
    assert outcome.relaxed == ("industry_scope",)
    assert len(outcome.candidates) == 7
    assert outcome.log_extra()["relaxed"] == ["industry_scope"]


def test_relaxation_stops_at_the_first_rung_that_reaches_the_floor():
    # Giving up more scope than the shortlist needs is not free.
    outcome = relax_to_floor(
        _pool(1), [("industry_scope", _pool(5)), ("other", _pool(40))], 5
    )
    assert outcome.relaxed == ("industry_scope",)
    assert len(outcome.candidates) == 5


def test_an_unreachable_floor_is_reported_not_faked():
    outcome = relax_to_floor(_pool(2), [("industry_scope", _pool(3))], 5)
    assert outcome.floor_unreached is True
    assert len(outcome.candidates) == 3          # the best it could do, honestly


def test_a_rung_can_never_shrink_the_pool():
    outcome = relax_to_floor(_pool(4), [("industry_scope", _pool(1))], 5)
    assert len(outcome.candidates) == 4


def test_applicability_and_stage_are_never_in_the_ladder():
    """Case 14, as a structural property rather than a scenario.

    The ladder cannot re-admit a hard contradiction because the only thing it
    can relax is industry. Asserted on the constant so that WIDENING the ladder
    later has to come past this test.
    """
    assert RELAXATION_LADDER == ("industry_scope",)
    assert "applicability" in NEVER_RELAXED
    assert "context_scope" in NEVER_RELAXED
    assert "stage_scope" in NEVER_RELAXED
    for rung in RELAXATION_LADDER:
        assert rung not in NEVER_RELAXED


# =========================================================== the removal record
def test_every_removal_records_which_token_was_unmet():
    result = filter_by_applicability(
        [q(1)], ctx(team_size="solo", business_model="B2B"),
        {1: frozenset({TOKEN_HAS_TEAM, "model:b2b"})},
    )
    # Only the token that actually contradicted, not every token on the row.
    assert result.removed == ((1, (TOKEN_HAS_TEAM,)),)


def test_the_filter_preserves_order_and_does_not_mutate_its_input():
    pool = [q(3), q(1), q(2)]
    before = list(pool)
    result = filter_by_applicability(pool, ctx(team_size="6_10"), {1: frozenset({TOKEN_HAS_TEAM})})
    assert [x.question_id for x in result.kept] == [3, 1, 2]
    assert pool == before


def test_a_missing_precondition_map_gates_nothing():
    # Any database that has not run b7c2d94e5f10 -- fail open, like every other
    # optional map in this package.
    result = filter_by_applicability([q(1)], ctx(team_size="solo"), None)
    assert len(result.kept) == 1
    assert isinstance(result, ApplicabilityResult)
