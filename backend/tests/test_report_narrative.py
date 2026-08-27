"""Report Narrative Generator (#20) -- the hard-rule + safety tests.

The generator is pure given a ReportPayload, so these need no DB.
"""

import re
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1.reports.generator import ReportNarrativeGenerator
from app.api.v1.reports.payload import (
    ActionItem, ArchetypeFinding, PillarFinding, ReportPayload, RootCauseFinding,
)
from app.api.v1.reports.variants import ReportVariant, select_variant


def _pillar(name, score, flag=False, note=None, band="Developing", desc=None):
    return PillarFinding(pillar_id=1, name=name, score=score, band=band,
                         band_description=desc, red_flag_triggered=flag, red_flag_note=note)


def _payload(**over):
    base = dict(
        report_id=1, founder_id=7, session_id=3, founder_name="Rahul",
        tone_code="PROMPT-STAGE01-TONE", tone_persona="Compass",
        session_state="stable", distress_acknowledged_first=False,
        overall_confidence_score=85.0,
        business_health_overall=64, business_health_band="Needs Attention",
        pillars=(_pillar("Founder Readiness", 62), _pillar("Market Clarity", 48)),
        red_flag_pillars=(),
        archetype=ArchetypeFinding("Operator", "ARCH-002", "Mastery", True, 0.31),
        top_root_causes=(
            RootCauseFinding(10, "Weak pipeline", "Sales & Revenue", "confirmed", True, 1),
            RootCauseFinding(11, "Unclear ICP", "Go-To-Market", "not_tested", True, 2),
        ),
        confirm_actions=(ActionItem(5, 1, ("Confirm your ICP",), "why"),),
        solve_actions=(ActionItem(6, 1, ("Build a pipeline tracker",), "why"),),
        category_risk_scores={"Sales & Revenue": 0.6, "Founder Psychology": 0.1},
    )
    base.update(over)
    return ReportPayload(**base)


def _gen(payload, **kw):
    return ReportNarrativeGenerator().generate(payload, **kw)


def _keys(n):
    return [s.key for s in n.sections]


# 1. No number appears in prose that is not in the payload.
def test_no_fabricated_numbers():
    p = _payload(pillars=(_pillar("Founder Readiness", 62), _pillar("Market Clarity", 30, True,
                 "A score below 35% triggers Section H.")))
    n = _gen(p)
    allowed = {"100"}  # fixed scale denominator ("out of 100"), a template constant
    allowed.update(str(x) for x in (p.business_health_overall,) if x is not None)
    for pf in p.pillars:
        if pf.score is not None:
            allowed.add(str(pf.score))
        allowed.update(re.findall(r"\d+", pf.red_flag_note or ""))
    for s in n.sections:
        for tok in re.findall(r"\d+", s.prose):
            assert tok in allowed, f"prose number {tok!r} not in payload ({s.key}): {s.prose!r}"


# 2. Distress variant + acknowledgement precedes any business content.
def test_distress_variant_ack_first():
    n = _gen(_payload(distress_acknowledged_first=True), distress_protocol="STOP the diagnostic. Acknowledge.")
    assert n.variant is ReportVariant.DISTRESS
    keys = _keys(n)
    assert keys[0] == "acknowledgement"
    ack = keys.index("acknowledgement")
    support = keys.index("support_recommendation")
    for biz in ("business_dna", "problem_path"):
        if biz in keys:
            assert ack < keys.index(biz) and support < keys.index(biz)


# 3. No-clear-diagnosis does not assert a diagnosis.
def test_no_clear_diagnosis_does_not_assert():
    p = _payload(category_risk_scores={"Sales & Revenue": 0.2, "Product": 0.1, "Team & Leadership": 0.15})
    n = _gen(p)
    assert n.variant is ReportVariant.NO_CLEAR_DIAGNOSIS
    keys = _keys(n)
    assert "areas_to_monitor" in keys and "problem_path" not in keys
    prose = " ".join(s.prose for s in n.sections).lower()
    assert "no single critical issue" in prose
    for word in ("we confirmed", "primary driver", "root cause is"):
        assert word not in prose


# 4. Psychology precedence: leads even when a business category scores higher.
def test_psychology_precedence():
    p = _payload(category_risk_scores={"Sales & Revenue": 0.9, "Founder Psychology": 0.5})
    assert p.psychology_flagged is True
    n = _gen(p)
    keys = _keys(n)
    assert "psychological_note" in keys
    assert keys.index("psychological_note") < keys.index("business_dna")
    assert keys.index("psychological_note") < keys.index("problem_path")


# 5. A pillar red flag surfaces despite a healthy overall score.
def test_pillar_red_flag_despite_healthy_overall():
    p = _payload(
        business_health_overall=82,  # healthy
        pillars=(_pillar("Founder Readiness", 30, True, "Below 35% triggers Section H."),
                 _pillar("Market Clarity", 78)),
        red_flag_pillars=(_pillar("Founder Readiness", 30, True, "Below 35% triggers Section H."),),
    )
    n = _gen(p)
    keys = _keys(n)
    assert "psychological_note" in keys
    biz = next(s for s in n.sections if s.key == "business_dna")
    assert "Founder Readiness" in biz.facts["red_flag_pillars"]


# 6. Shared view is a strict subset of the owner view.
def test_shared_is_strict_subset():
    n = _gen(_payload())
    owner_headings = {s.heading for s in n.sections if s.prose}
    shared = [{"heading": s.heading, "prose": s.prose} for s in n.sections if s.prose]
    shared_headings = {d["heading"] for d in shared}
    assert shared_headings <= owner_headings
    # No facts / IDs leak into the shared serialization.
    blob = str(shared)
    assert "intervention_id" not in blob and "facts" not in blob
    # Owner carries facts that shared does not.
    assert any(s.facts for s in n.sections)


# 7. Cross-founder access -> 403; missing -> 404.
def test_cross_founder_forbidden_and_missing_not_found():
    from app.api.v1.reports.routes import _owned_report

    class _DB:
        def __init__(self, rep): self._rep = rep
        def get(self, model, rid): return self._rep

    founder = SimpleNamespace(founder_id=7)
    other = SimpleNamespace(report_id=1, founder_id=999)  # someone else's report
    with pytest.raises(HTTPException) as e:
        _owned_report(_DB(other), founder, 1)
    assert e.value.status_code == 403

    with pytest.raises(HTTPException) as e:
        _owned_report(_DB(None), founder, 1)
    assert e.value.status_code == 404


def test_tentative_archetype_wording():
    # Hard rule 4: a thin-margin archetype is presented tentatively.
    n = _gen(_payload(archetype=ArchetypeFinding("Catalyst", "ARCH-006", "Possibility", False, 0.16)))
    fd = next(s for s in n.sections if s.key == "founder_dna")
    assert fd.facts["archetype"]["tentative"] is True
    assert "hypothesis" in fd.prose.lower() or "lean toward" in fd.prose.lower()


def test_not_tested_reads_differently_from_confirmed():
    # Hard rule 5.
    n = _gen(_payload())
    pp = next(s for s in n.sections if s.key == "problem_path").prose.lower()
    assert "confirmed" in pp and ("did not directly test" in pp or "not directly test" in pp)


# Feedback #2: bands + descriptions, never raw numbers.
def test_business_dna_shows_bands_not_raw_numbers():
    n = _gen(_payload())
    assert n.exposes_numeric_scores is False
    biz = next(s for s in n.sections if s.key == "business_dna")
    assert "overall_band" in biz.facts and "overall_score" not in biz.facts
    for pf in biz.facts["pillars"]:
        assert "band" in pf and "score" not in pf
    assert not re.search(r"\d", biz.prose)  # no raw numbers reach the founder


# Feedback #3: Section H is a named, spec-defined section on Critical Gap.
def test_psychological_note_uses_band_description_and_hides_internals():
    desc = ("The founder is psychologically unprepared for the demands of this journey "
            "right now. The report will include Section H (Psychological State Note).")
    fr = _pillar("Founder Readiness", 20, flag=True, note="flag", band="Critical Gap", desc=desc)
    p = _payload(business_health_overall=70, business_health_band="Developing",
                 pillars=(fr, _pillar("Market Clarity", 60)), red_flag_pillars=(fr,))
    n = _gen(p)
    sec = next(s for s in n.sections if s.key == "psychological_note")
    # The band description still drives the prose -- that part is unchanged.
    assert "psychologically unprepared" in sec.prose

    # But the internal routing keys must not reach the founder. A real report
    # printed "Section: H" and "Trigger: founder_readiness_critical_gap" as
    # label/value pairs beside the most personal section in the document.
    assert "section" not in sec.facts
    assert "trigger" not in sec.facts
    assert "Section H" not in sec.heading
    assert sec.heading == "Before the business — how you're doing"
    # The same paragraph is NOT duplicated inside Business DNA.
    biz = next(s for s in n.sections if s.key == "business_dna")
    assert "psychologically unprepared" not in biz.prose


# Feedback #5: which narrator produced the report is recorded.
def test_narrator_provenance_recorded():
    n = _gen(_payload())
    assert n.narrator_provenance["narrator"] == "TemplateNarrator"
    assert n.narrator_provenance["degraded"] is False


def test_llm_fallback_is_visible_not_silent():
    from app.api.v1.reports.narrator import LLMSectionNarrator

    def boom(_prompt):
        raise RuntimeError("model down")

    n = ReportNarrativeGenerator(LLMSectionNarrator(boom)).generate(_payload())
    assert n.narrator_provenance["degraded"] is True
    assert n.narrator_provenance["by_source"].get("llm_fallback_template", 0) > 0


# ---- Phase 1 blocking-bug regressions -----------------------------------
_PROTOCOL = ("STOP the diagnostic immediately — do not continue to business questions. "
             "Do not offer solutions. Do not validate the catastrophic thinking.")

def test_distress_ack_never_quotes_the_internal_protocol():
    n = _gen(_payload(distress_acknowledged_first=True), distress_protocol=_PROTOCOL)
    ack = next(s for s in n.sections if s.key == "acknowledgement").prose
    for leaked in ("STOP the diagnostic", "Do not offer solutions",
                   "Do not validate", "catastrophic thinking"):
        assert leaked not in ack
    assert "how you are doing comes first" in ack.lower()

def test_psychological_note_never_prints_session_framing():
    # psychology flagged by category only (no Section H, no red flag) -> must not
    # fall back to the report_framing_adjustment directive.
    framing = "Report is de-prioritised. Lead with acknowledgement of difficulty."
    p = _payload(category_risk_scores={"Founder Psychology": 0.5, "Sales & Revenue": 0.9},
                 pillars=(_pillar("Founder Readiness", 60),), red_flag_pillars=())
    n = _gen(p, session_framing=framing)
    note = next(s for s in n.sections if s.key == "psychological_note").prose
    assert "de-prioritised" not in note and "Lead with acknowledgement" not in note
    assert note  # still produces founder-facing copy

def test_priority_actions_lists_the_actual_actions():
    n = _gen(_payload())
    pa = next(s for s in n.sections if s.key == "priority_actions").prose
    assert "Confirm your ICP" in pa and "Build a pipeline tracker" in pa

def test_no_double_the_article():
    n = _gen(_payload(archetype=ArchetypeFinding("The Operator", "ARCH-002", "Mastery", True, 0.3)))
    fd = next(s for s in n.sections if s.key == "founder_dna").prose
    assert "the The" not in fd and "The Operator" in fd

def test_discovery_cta_present_in_standard_absent_in_distress():
    std = _gen(_payload())
    assert std.sections[-1].key == "discovery_cta"
    dis = _gen(_payload(distress_acknowledged_first=True), distress_protocol=_PROTOCOL)
    assert "discovery_cta" not in [s.key for s in dis.sections]

def test_business_dna_is_brief_under_distress():
    desc = "The founder is making some sales but does not have a repeatable process. " * 2
    p = _payload(distress_acknowledged_first=True,
                 pillars=(_pillar("Revenue Maturity", 40, band="Needs Attention", desc=desc),))
    n = _gen(p, distress_protocol=_PROTOCOL)
    biz = next(s for s in n.sections if s.key == "business_dna").prose
    assert "it can wait" in biz.lower()
    assert desc.strip() not in biz  # full six-pillar audit is NOT dumped under distress

def test_expected_impact_is_declared_unpopulated_not_silently_missing():
    n = _gen(_payload())
    assert "expected_impact" in n.unpopulated_sections
    # and it is genuinely empty, not fabricated into a rendered section
    assert "expected_impact" not in [s.key for s in n.sections]


def test_identity_fusion_separation_language_wired_from_payload():
    fr = _pillar("Founder Readiness", 30, flag=True, band="Critical Gap",
                 desc="Burnout and isolation are active blockers.")
    p = _payload(pillars=(fr,), red_flag_pillars=(fr,), separate_identity=True)
    n = _gen(p)  # no explicit separate_identity kwarg -> must come from payload
    note = next(s for s in n.sections if s.key == "psychological_note").prose
    assert "You are not those challenges" in note


# --- Fix regression: Section H must not fire for an UNRELATED pillar red flag --
def test_unrelated_pillar_red_flag_does_not_trigger_section_h():
    # Financial Runway is red-flagged; Founder Readiness is healthy and not
    # flagged. Section H is Founder-Readiness-specific -- it must not render
    # with empty content just because some other pillar is red-flagged (that
    # used to hand the LLM narrator nothing to work with, and it fabricated a
    # claim to fill the section).
    runway = _pillar("Financial Runway", 22, flag=True, band="Critical Gap",
                     note="Runway under three months is a red flag.")
    p = _payload(
        pillars=(_pillar("Founder Readiness", 60, band="Developing"), runway),
        red_flag_pillars=(runway,),
    )
    assert p.psychology_flagged is False
    n = _gen(p)
    assert "psychological_note" not in _keys(n)
    # the red flag still surfaces -- via Business DNA, not a fabricated Section H
    biz = next(s for s in n.sections if s.key == "business_dna")
    assert "Financial Runway" in biz.prose


def test_founder_readiness_red_flag_still_triggers_section_h():
    fr = _pillar("Founder Readiness", 28, flag=True, band="Critical Gap",
                 desc="Running on empty affects every decision that follows.")
    p = _payload(pillars=(fr, _pillar("Market Clarity", 55)), red_flag_pillars=(fr,))
    n = _gen(p)
    assert "psychological_note" in _keys(n)


# --- Fix regression: areas_to_monitor slots carry NAMES only, never the score --
def test_areas_to_monitor_slots_have_no_raw_score():
    p = _payload(category_risk_scores={"Go-To-Market": 0.2, "Product": 0.18, "Sales & Revenue": 0.12})
    gen = ReportNarrativeGenerator()
    slots, facts = gen._slots_and_facts("areas_to_monitor", p, False)
    assert slots == {"categories": ["Go-To-Market", "Product", "Sales & Revenue"]}
    assert facts == slots
    for v in slots["categories"]:
        assert isinstance(v, str)  # not a (name, score) tuple


# --- Fix regression: the LLM prompt instructs brevity when slots["brief"] ------
def test_llm_prompt_includes_brief_directive_when_flagged():
    from app.api.v1.reports.narrator import LLMSectionNarrator, ToneGuidance

    captured = {}
    def fake_llm(prompt):
        captured["prompt"] = prompt
        return "A brief note on the business."

    narrator = LLMSectionNarrator(fake_llm)
    narrator.narrate("business_dna", {"overall_band": "Needs Attention", "brief": True}, ToneGuidance("Validator"))
    assert "BRIEF" in captured["prompt"] and "one short sentence" in captured["prompt"].lower()


def test_llm_prompt_omits_brief_directive_when_not_flagged():
    from app.api.v1.reports.narrator import LLMSectionNarrator, ToneGuidance

    captured = {}
    def fake_llm(prompt):
        captured["prompt"] = prompt
        return "prose"

    narrator = LLMSectionNarrator(fake_llm)
    narrator.narrate("business_dna", {"overall_band": "Needs Attention"}, ToneGuidance("Validator"))
    assert "IMPORTANT: this section must be BRIEF" not in captured["prompt"]


# --- the hero paragraph stays a paragraph ----------------------------------
# The founder-facing report opens with this prose. Founders type essays into
# the vision box, and every one of those characters used to land in the hero
# verbatim, quoted whole. These pin the limit that the section's own comment
# had promised since it was written but never enforced.

_ESSAY = (
    "I want a business that runs without me being in every single decision, "
    "where the team knows what good looks like and does not need me to tell "
    "them, and where I can take three weeks off without anything catching "
    "fire or anybody calling me about it. That is the whole thing really."
)


def _dna(**over):
    return next(s for s in _gen(_payload(**over)).sections if s.key == "founder_dna").prose


def test_a_long_vision_is_not_quoted_whole_into_the_hero():
    prose = _dna(founder_vision=_ESSAY)
    assert _ESSAY not in prose
    assert "runs without me" in prose            # still the founder's own words
    assert len(prose) < 500


def test_a_long_vision_is_cut_at_a_sentence_when_the_first_one_fits():
    """A whole first thought, kept whole. _ESSAY does NOT take this path: its
    own first sentence runs 275 characters, so it falls to the word cut below
    -- which is the point of having both rules."""
    essay = "A business that runs without me. " + "There is a lot more I could say about it. " * 6
    prose = _dna(founder_vision=essay)
    quoted = prose.split('this is what success looks like: "')[1].split('"')[0]
    assert quoted == "A business that runs without me."


def test_a_short_vision_is_left_exactly_as_written():
    prose = _dna(founder_vision="Runs without me.")
    assert '"Runs without me."' in prose


def test_a_single_endless_sentence_is_cut_at_a_word_boundary():
    prose = _dna(founder_vision="I want " + "a much calmer business " * 20)
    quoted = prose.split('this is what success looks like: "')[1].split('"')[0]
    assert quoted.endswith("…")
    assert quoted.rstrip("…").strip() in " ".join(("I want " + "a much calmer business " * 20).split())


def test_the_earliest_terminator_wins_not_the_first_one_looked_for():
    """Scanning "." before "!" would return the second sentence."""
    prose = _dna(founder_vision="Ship it! Then rest for a while.")
    assert '"Ship it!"' in prose


def test_every_narrated_dimension_is_shortened_not_just_vision():
    prose = _dna(founder_vision=_ESSAY,
                 strengths_blind_spots=(_ESSAY,),
                 phase2_dimensions={"purpose_mission": (_ESSAY,)})
    assert _ESSAY not in prose
    assert prose.count(_ESSAY[:40]) <= 3         # each appears once, shortened


def test_a_question_stored_as_an_answer_is_never_narrated_back():
    """Live data defect: some strengths_blind_spots rows hold the QUESTION.
    Narrating one produces "A pattern worth naming: Tell me about..."."""
    q = "Tell me about the last time a strength of yours became a problem?"
    prose = _dna(strengths_blind_spots=(q,))
    assert "A pattern worth naming" not in prose
    assert "Tell me about" not in prose


def test_a_real_blind_spot_still_gets_narrated():
    prose = _dna(strengths_blind_spots=("You hold on to decisions too long.",))
    assert "A pattern worth naming: You hold on to decisions too long." in prose
