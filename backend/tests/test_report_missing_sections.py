"""The sections a founder was not getting, and the reason two of them were empty.

Two separate defects, found by generating a real report end to end on
2026-08-19:

  * The distress report opened with "I don't have enough information to write
    this section -- no facts were provided to draw from." twice. Those are the
    first two things a founder in distress reads. `acknowledgement` and
    `support_recommendation` carry no slots by design -- they are fixed,
    carefully-worded copy the TemplateNarrator already holds -- but they were
    still sent to the LLM, which under a strict never-invent instruction and no
    facts can only refuse or fabricate. It refused, and the refusal was a
    non-empty string, so the existing fallback never fired.

  * `supporting_evidence`, `recommended_roadmap` and `why_steps` were declared
    "no backend source" and shipped absent, while their source data sat on the
    payload unused. The founder got a root cause and three actions with no
    evidence trail, no sequencing and no reason for any of them.

`expected_impact` is genuinely sourceless and stays absent -- that distinction
is the point, so it is asserted here too.
"""

from __future__ import annotations

from app.api.v1.reports.generator import UNPOPULATED_SECTIONS, ReportNarrativeGenerator
from app.api.v1.reports.narrator import (
    LLMSectionNarrator,
    TemplateNarrator,
    ToneGuidance,
)
from app.api.v1.reports.payload import (
    ActionItem,
    ArchetypeFinding,
    PillarFinding,
    ReportPayload,
    RootCauseFinding,
)


def _pillar(name, score, band="Developing"):
    return PillarFinding(pillar_id=1, name=name, score=score, band=band,
                         band_description=None, red_flag_triggered=False,
                         red_flag_note=None)


def _payload(**over):
    base = dict(
        report_id=1, founder_id=7, session_id=3, founder_name="Kavya",
        tone_code="PROMPT-STAGE01-TONE", tone_persona="Validator",
        session_state="stable", distress_acknowledged_first=False,
        overall_confidence_score=85.0,
        business_health_overall=40, business_health_band="Needs Attention",
        pillars=(_pillar("Founder Readiness", 55), _pillar("Market Clarity", 30)),
        red_flag_pillars=(),
        archetype=ArchetypeFinding("Operator", "ARCH-002", "Mastery", True, 0.62),
        top_root_causes=(
            RootCauseFinding(10, "Untested pricing", "Sales & Revenue", "confirmed", True, 1),
            RootCauseFinding(11, "No ICP evidence", "Go-To-Market", "not_tested", True, 2),
        ),
        confirm_actions=(ActionItem(5, 1, ("Cost one bedcover end to end",), "because X"),),
        solve_actions=(ActionItem(6, 1, ("Interview five non-buyers",), "because Y"),),
        stated_symptom="Nobody knows we exist, so it must be a marketing problem.",
        symptom_probes=(("What have you tried?", "Only Instagram, posted when I remember."),),
        category_risk_scores={"Sales & Revenue": 0.6, "Founder Psychology": 0.1},
    )
    base.update(over)
    return ReportPayload(**base)


def _sections(payload=None):
    n = ReportNarrativeGenerator().generate(payload or _payload())
    return {s.key: s for s in n.sections}


# --- the three sections that were declared sourceless ----------------------

def test_supporting_evidence_is_present_and_quotes_the_founders_own_probes():
    section = _sections()["supporting_evidence"]
    assert section.prose
    probes = section.facts["probes"]
    assert probes[0]["answer"] == "Only Instagram, posted when I remember."


def test_supporting_evidence_never_reads_an_untested_cause_as_settled():
    prose = _sections()["supporting_evidence"].prose
    assert "No ICP evidence" in prose
    assert "hypotheses" in prose or "tested" in prose


def test_recommended_roadmap_orders_confirm_before_solve():
    section = _sections()["recommended_roadmap"]
    assert section.facts["confirm_steps"][0]["next_actions"] == ["Cost one bedcover end to end"]
    assert section.facts["solve_steps"][0]["next_actions"] == ["Interview five non-buyers"]
    assert "confirm" in section.prose.lower()


def test_roadmap_prose_contains_no_digits():
    """test_no_fabricated_numbers guards the whole report; this pins the reason
    the roadmap in particular is worded without ordinals."""
    prose = _sections()["recommended_roadmap"].prose
    assert not any(ch.isdigit() for ch in prose)


def test_why_steps_rationale_never_reaches_founder_facing_facts():
    """Rationales can carry engine bookkeeping -- "Supported by 10 semantic
    evidence item(s)" -- and `facts` renders verbatim. That is exactly how
    red_flag_note reached a founder's screen. Rationale is a slot, never a fact.
    """
    section = _sections()["why_steps"]
    assert section.prose
    flat = repr(section.facts)
    assert "because X" not in flat and "because Y" not in flat


def test_sections_are_omitted_when_their_source_is_empty():
    bare = _payload(confirm_actions=(), solve_actions=(), symptom_probes=(),
                    top_root_causes=())
    keys = _sections(bare).keys()
    assert "recommended_roadmap" not in keys
    assert "why_steps" not in keys
    assert "supporting_evidence" not in keys


def test_expected_impact_stays_declared_unpopulated():
    """The one that really has no source. Nothing estimates an impact, so
    writing this section would mean inventing it."""
    assert UNPOPULATED_SECTIONS == ("expected_impact",)


# --- the placeholder-prose bug ---------------------------------------------

class _RefusingLLM:
    """Stands in for a model given a section with no facts. This is the actual
    string a live report shipped."""

    def __init__(self):
        self.prompts = []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        return ("I don't have enough information to write this section — no "
                "facts were provided to draw from.")


def test_contentless_sections_never_reach_the_model():
    llm = _RefusingLLM()
    narrator = LLMSectionNarrator(llm, fallback=TemplateNarrator())
    tone = ToneGuidance(persona="Validator")

    prose, source = narrator.narrate_with_source("acknowledgement", {}, tone)

    assert llm.prompts == [], "a section with no slots must not be sent to the model"
    assert source == "template_no_slots"
    assert "enough information" not in prose
    assert "what you are carrying" in prose


def test_flag_only_slots_still_count_as_contentless():
    """`wellbeing_first` / `brief` / `cta` steer a section's shape; they are not
    material to write about."""
    llm = _RefusingLLM()
    narrator = LLMSectionNarrator(llm, fallback=TemplateNarrator())
    tone = ToneGuidance(persona="Validator")

    _, source = narrator.narrate_with_source(
        "support_recommendation", {"wellbeing_first": True}, tone)

    assert llm.prompts == []
    assert source == "template_no_slots"


def test_sections_with_real_slots_still_go_to_the_model():
    llm = _RefusingLLM()
    narrator = LLMSectionNarrator(llm, fallback=TemplateNarrator())
    tone = ToneGuidance(persona="Validator")

    _, source = narrator.narrate_with_source(
        "founder_summary", {"founder_name": "Kavya"}, tone)

    assert len(llm.prompts) == 1
    assert source == "llm"


def test_a_zero_is_content_not_an_absence():
    llm = _RefusingLLM()
    narrator = LLMSectionNarrator(llm, fallback=TemplateNarrator())
    narrator.narrate_with_source("business_dna", {"score": 0}, ToneGuidance(persona="Auditor"))
    assert len(llm.prompts) == 1
