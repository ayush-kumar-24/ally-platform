"""Onboarding context reaches question selection.

The bug these cover: onboarding asks 20-30 questions to understand a founder
before the diagnosis begins, and none of it reached the advisor. It saw the last
five Q&A pairs, the question just asked and a shortlist -- so two founders in the
same stage group were asked the same questions in the same order, which is
exactly what was reported from the field.
"""

from types import SimpleNamespace

from app.api.v1.diagnosis.advisor import LLMNextQuestionAdvisor
from app.api.v1.diagnosis.founder_brief import build_founder_brief


class _NoDb:
    """A db that refuses every query -- proves the brief degrades rather than
    raising when the phase tables are unreadable (RLS, a dropped connection)."""

    def execute(self, *a, **k):
        raise RuntimeError("db unavailable")


def _founder(**overrides):
    base = dict(
        founder_id=1, stage=SimpleNamespace(stage_name="Early Traction"),
        industry="SaaS", current_revenue="above_1Cr", team_size="11_25",
        business_model="B2B", experience_level="one_company",
        building_summary="Compliance reporting for Indian manufacturers.",
        product_description=None, problem_statement="Churn is high.",
        customer_segment=["mid-size manufacturers"], current_challenges=None,
        goal_90_day="Cut churn to 3%", vision_1_year=None,
        founder_motivation="Watched good companies get fined.",
        decision_making_style="analytical", emotional_state=["determined", "stuck"],
        working_relationship="strategist", founder_reality_signals=None,
        business_reality_signals=None, invisible_gaps=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_brief_carries_what_onboarding_collected():
    brief = build_founder_brief(_NoDb(), _founder())
    for expected in ("Early Traction", "SaaS", "above_1Cr", "B2B",
                     "Compliance reporting", "Churn is high", "Cut churn to 3%",
                     "analytical", "strategist"):
        assert expected in brief, expected


def test_brief_omits_fields_the_founder_never_filled():
    """Empty fields are dropped, not rendered as "Not set".

    This runs on every answer of a 30-question diagnosis, so a line that says
    nothing is paid for thirty times. It also reads better: absent is absent.
    """
    brief = build_founder_brief(_NoDb(), _founder())
    assert "Product:" not in brief          # product_description was None
    assert "1-year vision" not in brief     # vision_1_year was None
    assert "None" not in brief and "null" not in brief


def test_brief_is_empty_for_a_founder_who_skipped_onboarding():
    """No header rather than an empty one -- a bare "FOUNDER CONTEXT" with
    nothing under it tells the model we looked and found nothing, which is
    worse than not raising the subject."""
    blank = SimpleNamespace(founder_id=2, stage=None, **{
        f: None for f in (
            "industry", "current_revenue", "team_size", "business_model",
            "experience_level", "building_summary", "product_description",
            "problem_statement", "customer_segment", "current_challenges",
            "goal_90_day", "vision_1_year", "founder_motivation",
            "decision_making_style", "emotional_state", "working_relationship",
            "founder_reality_signals", "business_reality_signals", "invisible_gaps")})
    assert build_founder_brief(_NoDb(), blank) == ""


def test_brief_survives_an_unreadable_database():
    """The phase excerpts are optional; the interview is not. A failing query
    must cost us the DNA section, never the turn."""
    brief = build_founder_brief(_NoDb(), _founder())
    assert brief                                    # profile half still rendered
    # The SECTION, not the word -- the header names Founder DNA either way.
    assert "Founder DNA (most recent)" not in brief
    assert "What they said the problem is" not in brief


def _prompt(brief: str) -> str:
    advisor = LLMNextQuestionAdvisor(provider=None)
    asked = SimpleNamespace(question_id=1, category="sales",
                            question_text="How do you sell today?")
    shortlist = [SimpleNamespace(question_id=7, category="sales",
                                 question_text="Who closes deals?")]
    return advisor._build_request(
        asked, "Founder-led selling.", shortlist, [("Prev q", "Prev a")], brief
    ).messages[1].content


def test_advisor_prompt_leads_with_the_founder_context():
    """Who they are, before what they just said."""
    prompt = _prompt(build_founder_brief(_NoDb(), _founder()))
    assert prompt.startswith("FOUNDER CONTEXT")
    assert "Churn is high" in prompt
    # and the original inputs are still there
    assert "Who closes deals?" in prompt and "Founder-led selling." in prompt


def test_advisor_prompt_unchanged_when_there_is_no_context():
    prompt = _prompt("")
    assert not prompt.startswith("FOUNDER CONTEXT")
    assert prompt.startswith("Recent Q&A:")


def test_advisor_is_told_to_use_the_context():
    """The block being present is not enough -- the system prompt has to say
    what to do with it, or the model treats it as decoration."""
    advisor = LLMNextQuestionAdvisor(provider=None)
    system = advisor._build_request(
        SimpleNamespace(question_id=1, category="c", question_text="q"),
        "a", [SimpleNamespace(question_id=2, category="c", question_text="q2")],
        [], "FOUNDER CONTEXT\nStage: Growth",
    ).messages[0].content
    assert "FOUNDER CONTEXT" in system
    assert "re-establishing" in system   # don't re-ask what they already told us
