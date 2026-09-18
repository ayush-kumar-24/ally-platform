"""FounderContext: the three-valued contract every later gate depends on.

The tests that matter most here are the UNKNOWN ones. A bug that turns UNKNOWN
into CONTRADICTED does not fail loudly -- it silently stops asking a whole class
of question to every founder whose onboarding was incomplete, and the diagnosis
still looks finished. So unknown-means-keep is asserted per family, not once.

No database, no LLM, no fixtures: a founder here is a SimpleNamespace, which is
the point of `from_founder` being pure.
"""

from types import SimpleNamespace

import pytest

from app.api.v1.diagnosis.founder_context import (
    ALL_FAMILIES,
    FAMILY_BUSINESS_MODEL,
    FAMILY_CHALLENGES,
    FAMILY_INDUSTRY,
    FAMILY_REVENUE,
    FAMILY_STAGE,
    FAMILY_TEAM,
    TOKEN_FUNDRAISING_INTENT,
    TOKEN_HAS_REVENUE,
    TOKEN_HAS_TEAM,
    Applicability,
    FounderContext,
    family_of,
)

SATISFIED = Applicability.SATISFIED
CONTRADICTED = Applicability.CONTRADICTED
UNKNOWN = Applicability.UNKNOWN


def founder(**overrides):
    """A founder row with everything unset unless a test sets it."""
    base = dict(
        stage=None, industry_mapped=None, team_size=None,
        business_model=None, current_revenue=None, current_challenges=None,
    )
    stage_order = overrides.pop("stage_order", None)
    if stage_order is not None:
        base["stage"] = SimpleNamespace(
            stage_order=stage_order, stage_name=overrides.pop("stage_name", "Growth / Scaling")
        )
    base.update(overrides)
    return SimpleNamespace(**base)


# --- the empty founder ------------------------------------------------------
def test_a_founder_we_know_nothing_about_has_every_family_unknown():
    ctx = FounderContext.from_founder(founder())
    assert ctx.unknowns == ALL_FAMILIES
    assert ctx.tokens == frozenset()
    assert ctx.denied == frozenset()


def test_every_precondition_is_unknown_not_contradicted_for_an_empty_founder():
    # The single most important property in this file. If any of these ever
    # returns CONTRADICTED, questions silently disappear for every founder
    # whose onboarding is incomplete.
    ctx = FounderContext.from_founder(founder())
    for token in (TOKEN_HAS_TEAM, TOKEN_HAS_REVENUE, TOKEN_FUNDRAISING_INTENT,
                  "industry:agritech", "model:b2b", "team:2_5", "stage:5"):
        assert ctx.verdict(token) is UNKNOWN, token


def test_no_precondition_at_all_is_satisfied():
    # A question with no precondition is universal; that is the default for all
    # but a curated few tags.
    ctx = FounderContext.from_founder(founder())
    assert ctx.verdict(None) is SATISFIED
    assert ctx.verdict("") is SATISFIED


# --- team -------------------------------------------------------------------
def test_solo_contradicts_has_team():
    ctx = FounderContext.from_founder(founder(team_size="solo"))
    assert ctx.verdict(TOKEN_HAS_TEAM) is CONTRADICTED
    assert ctx.verdict("team:solo") is SATISFIED
    assert FAMILY_TEAM not in ctx.unknowns


@pytest.mark.parametrize("size", ["2_5", "6_10", "11_25", "26_50", "50_plus"])
def test_every_non_solo_bucket_satisfies_has_team(size):
    ctx = FounderContext.from_founder(founder(team_size=size))
    assert ctx.verdict(TOKEN_HAS_TEAM) is SATISFIED
    assert ctx.verdict(f"team:{size}") is SATISFIED
    # ...and contradicts the buckets it is not, because the family is answered.
    assert ctx.verdict("team:solo") is CONTRADICTED


def test_unset_team_size_keeps_team_questions_eligible():
    ctx = FounderContext.from_founder(founder(team_size=None))
    assert ctx.verdict(TOKEN_HAS_TEAM) is UNKNOWN
    assert ctx.is_unknown_family(TOKEN_HAS_TEAM) is True


def test_blank_team_size_is_unknown_not_a_value():
    ctx = FounderContext.from_founder(founder(team_size="   "))
    assert ctx.verdict(TOKEN_HAS_TEAM) is UNKNOWN


# --- industry ---------------------------------------------------------------
def test_industry_code_passed_explicitly_wins():
    ctx = FounderContext.from_founder(founder(), industry_code="agritech")
    assert ctx.industry_code == "agritech"
    assert ctx.verdict("industry:agritech") is SATISFIED


def test_a_known_industry_contradicts_every_other_industry():
    # This is what makes industry gating work without enumerating 30 industries.
    ctx = FounderContext.from_founder(founder(), industry_code="agritech")
    assert ctx.verdict("industry:fintech") is CONTRADICTED
    assert ctx.verdict("industry:saas") is CONTRADICTED


def test_an_unknown_industry_contradicts_nothing():
    ctx = FounderContext.from_founder(founder())
    assert ctx.verdict("industry:agritech") is UNKNOWN
    assert ctx.verdict("industry:fintech") is UNKNOWN
    assert ctx.knows_industry is False


def test_industry_comes_from_the_loaded_relationship_when_not_passed():
    row = founder(industry_mapped=SimpleNamespace(industry_code="healthtech"))
    ctx = FounderContext.from_founder(row)
    assert ctx.industry_code == "healthtech"


def test_industry_code_is_normalised_to_lower_case():
    ctx = FounderContext.from_founder(founder(), industry_code="AgriTech")
    assert ctx.industry_code == "agritech"
    assert ctx.verdict("industry:agritech") is SATISFIED


def test_an_industry_id_we_cannot_name_is_unknown_not_contradicted():
    # industry_mapped_id set but the relationship unavailable: we cannot gate on
    # an id whose code we do not have, and guessing would be worse than asking.
    row = founder(industry_mapped_id=5, industry_mapped=None)
    ctx = FounderContext.from_founder(row)
    assert ctx.knows_industry is False
    assert ctx.verdict("industry:agritech") is UNKNOWN


# --- stage / business model / revenue --------------------------------------
def test_stage_order_becomes_a_token():
    ctx = FounderContext.from_founder(founder(stage_order=5))
    assert ctx.stage_order == 5
    assert ctx.verdict("stage:5") is SATISFIED
    assert ctx.verdict("stage:1") is CONTRADICTED


def test_a_boolean_is_not_a_stage_order():
    # bool is an int in Python; letting True through would emit "stage:True".
    ctx = FounderContext.from_founder(founder(stage=SimpleNamespace(stage_order=True)))
    assert ctx.stage_order is None
    assert FAMILY_STAGE in ctx.unknowns


def test_business_model_token():
    ctx = FounderContext.from_founder(founder(business_model="B2B"))
    assert ctx.verdict("model:b2b") is SATISFIED
    assert ctx.verdict("model:b2c") is CONTRADICTED


def test_pre_revenue_contradicts_has_revenue():
    ctx = FounderContext.from_founder(founder(current_revenue="pre_revenue"))
    assert ctx.verdict(TOKEN_HAS_REVENUE) is CONTRADICTED
    assert FAMILY_REVENUE not in ctx.unknowns


@pytest.mark.parametrize("band", ["under_1L", "1L_5L", "5L_25L", "25L_1Cr", "above_1Cr"])
def test_every_real_revenue_band_satisfies_has_revenue(band):
    ctx = FounderContext.from_founder(founder(current_revenue=band))
    assert ctx.verdict(TOKEN_HAS_REVENUE) is SATISFIED


# --- challenges and the fundraising asymmetry -------------------------------
def test_ticking_fundraising_satisfies_the_intent_token():
    ctx = FounderContext.from_founder(founder(current_challenges=["Fundraising", "Growth"]))
    assert ctx.verdict(TOKEN_FUNDRAISING_INTENT) is SATISFIED


def test_not_ticking_fundraising_is_unknown_never_contradicted():
    # "Biggest challenge, pick up to three" -- a founder mid-raise who is more
    # worried about sales will not tick it. Absence is not evidence.
    ctx = FounderContext.from_founder(founder(current_challenges=["Growth", "Sales & Marketing"]))
    assert ctx.verdict(TOKEN_FUNDRAISING_INTENT) is UNKNOWN


def test_fundraising_label_matches_case_insensitively_but_not_as_a_substring():
    assert FounderContext.from_founder(
        founder(current_challenges=["fundraising"])
    ).verdict(TOKEN_FUNDRAISING_INTENT) is SATISFIED
    assert FounderContext.from_founder(
        founder(current_challenges=["Fundraising timeline"])
    ).verdict(TOKEN_FUNDRAISING_INTENT) is UNKNOWN


@pytest.mark.parametrize("raw", [None, [], "Fundraising", {"a": 1}, [None, ""], 42])
def test_malformed_challenges_are_unknown_and_never_raise(raw):
    ctx = FounderContext.from_founder(founder(current_challenges=raw))
    assert FAMILY_CHALLENGES in ctx.unknowns
    assert ctx.verdict(TOKEN_FUNDRAISING_INTENT) is UNKNOWN


# --- session facts ----------------------------------------------------------
def test_a_session_fact_settles_an_unknown_family():
    ctx = FounderContext.from_founder(founder())
    assert ctx.verdict(TOKEN_HAS_TEAM) is UNKNOWN
    learned = ctx.with_session_facts({TOKEN_HAS_TEAM: False})
    assert learned.verdict(TOKEN_HAS_TEAM) is CONTRADICTED
    assert FAMILY_TEAM not in learned.unknowns


def test_a_session_fact_never_overrides_a_stated_profile_value():
    # Profile beats inference. A founder who said "2-5 people" keeps has_team
    # even if one answer looked otherwise; the disagreement is a data-quality
    # signal to log, not a silent correction.
    ctx = FounderContext.from_founder(founder(team_size="2_5"))
    learned = ctx.with_session_facts({TOKEN_HAS_TEAM: False})
    assert learned.verdict(TOKEN_HAS_TEAM) is SATISFIED


def test_session_facts_return_a_new_object_and_leave_the_original_alone():
    ctx = FounderContext.from_founder(founder())
    learned = ctx.with_session_facts({TOKEN_HAS_TEAM: False})
    assert learned is not ctx
    assert ctx.verdict(TOKEN_HAS_TEAM) is UNKNOWN


def test_empty_or_unusable_facts_are_a_no_op():
    ctx = FounderContext.from_founder(founder())
    assert ctx.with_session_facts(None) is ctx
    assert ctx.with_session_facts({}) is ctx
    assert ctx.with_session_facts({"": False}) is ctx
    assert ctx.with_session_facts({"not_a_known_token": False}) is ctx


def test_a_positive_session_fact_also_works():
    ctx = FounderContext.from_founder(founder())
    learned = ctx.with_session_facts({TOKEN_HAS_TEAM: True})
    assert learned.verdict(TOKEN_HAS_TEAM) is SATISFIED


# --- token/family plumbing --------------------------------------------------
@pytest.mark.parametrize("token,expected", [
    (TOKEN_HAS_TEAM, FAMILY_TEAM),
    (TOKEN_HAS_REVENUE, FAMILY_REVENUE),
    (TOKEN_FUNDRAISING_INTENT, FAMILY_CHALLENGES),
    ("industry:agritech", FAMILY_INDUSTRY),
    ("team:solo", FAMILY_TEAM),
    ("model:b2b", FAMILY_BUSINESS_MODEL),
    ("stage:5", FAMILY_STAGE),
    ("challenge:growth", FAMILY_CHALLENGES),
])
def test_family_of_recognised_tokens(token, expected):
    assert family_of(token) == expected


@pytest.mark.parametrize("token", ["", None, "nonsense", "unknown:thing", "industry:"])
def test_unrecognised_tokens_have_no_family(token):
    assert family_of(token) is None


def test_an_unrecognised_precondition_keeps_the_question_eligible():
    # A curation typo in question_tags.precondition_token must not silently
    # delete questions. Validation catches it; the interview does not stop.
    ctx = FounderContext.from_founder(founder(team_size="solo"), industry_code="agritech")
    assert ctx.verdict("typo_token") is UNKNOWN
    assert ctx.verdict("unknown:thing") is UNKNOWN


# --- immutability and logging ----------------------------------------------
def test_context_is_frozen():
    ctx = FounderContext.from_founder(founder())
    with pytest.raises(Exception):
        ctx.stage_order = 3  # type: ignore[misc]


def test_describe_is_log_safe_and_carries_no_free_text():
    ctx = FounderContext.from_founder(
        founder(stage_order=5, team_size="solo", business_model="B2B",
                current_revenue="1L_5L", current_challenges=["Fundraising"]),
        industry_code="agritech",
    )
    described = ctx.describe()
    assert described["industry"] == "agritech"
    assert described["team_size"] == "solo"
    assert described["fundraising_intent"] is True
    # The founder's own words never reach a log line through this path.
    assert "challenges" not in described
    assert "stage_name" not in described


def test_a_fully_known_founder_has_no_unknown_families():
    ctx = FounderContext.from_founder(
        founder(stage_order=4, team_size="6_10", business_model="B2B",
                current_revenue="5L_25L", current_challenges=["Fundraising"]),
        industry_code="agritech",
    )
    assert ctx.unknowns == frozenset()


# --- the personas from the QA matrix ---------------------------------------
def test_persona_a_solo_agritech_stage_0():
    ctx = FounderContext.from_founder(
        founder(stage_order=1, team_size="solo", business_model="B2C",
                current_revenue="pre_revenue", current_challenges=["Growth"]),
        industry_code="agritech",
    )
    assert ctx.verdict(TOKEN_HAS_TEAM) is CONTRADICTED          # no team questions
    assert ctx.verdict("industry:agritech") is SATISFIED        # agritech allowed
    assert ctx.verdict("industry:saas") is CONTRADICTED         # SaaS-only excluded
    assert ctx.verdict(TOKEN_FUNDRAISING_INTENT) is UNKNOWN     # not stated -> keep
    assert ctx.verdict(None) is SATISFIED                       # universal allowed


def test_persona_b_small_team_agritech_stage_0_to_1():
    ctx = FounderContext.from_founder(
        founder(stage_order=3, team_size="2_5", current_revenue="under_1L"),
        industry_code="agritech",
    )
    assert ctx.verdict(TOKEN_HAS_TEAM) is SATISFIED
    assert ctx.verdict("industry:agritech") is SATISFIED
    assert FAMILY_BUSINESS_MODEL in ctx.unknowns                # never collected


def test_persona_c_team_agritech_growth():
    ctx = FounderContext.from_founder(
        founder(stage_order=5, team_size="11_25", current_revenue="above_1Cr",
                current_challenges=["Scaling", "Fundraising"]),
        industry_code="agritech",
    )
    assert ctx.verdict(TOKEN_HAS_TEAM) is SATISFIED
    assert ctx.verdict(TOKEN_FUNDRAISING_INTENT) is SATISFIED
    assert ctx.verdict(TOKEN_HAS_REVENUE) is SATISFIED
