"""The report document renders the narrative it was given -- all of it.

build_report_document used to consult exactly three narrative keys
(psychological_note, founder_dna, problem_path) and derive everything else
straight from `insights`. Two things followed, and both reached founders:

  * every other section the generator wrote -- the evidence trail, the
    sequencing, why those steps, areas to monitor, the CTA -- was assembled,
    stored on narrative_snapshot, served by the JSON API, and then silently
    dropped from the page, the share link and the PDF. The tests that were
    supposed to guarantee those sections asserted on the GENERATOR's output, so
    they passed the whole time.

  * the report VARIANTS were decorative. The root cause came from
    insights["top_root_causes"], which exists regardless of variant, so a
    founder whose diagnosis was inconclusive still read a confident verdict,
    and a founder in distress was led with a business-health ring instead of
    the wellbeing copy the distress variant exists for.

These pin the document against the narrative rather than against the raw
pipeline output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

import pytest

from app.api.v1.reports.document import build_report_document


@dataclass
class _Section:
    key: str
    heading: str
    prose: str = ""
    facts: Mapping[str, Any] = field(default_factory=dict)


@dataclass
class _Narrative:
    sections: tuple[_Section, ...]


@pytest.fixture
def insights() -> dict:
    return {
        "business_health_score": {
            "band": "Critical Gap", "overall_score": "31",
            "pillars": [
                {"pillar_name": "Founder Readiness", "score": "20", "weight": "25.00"},
                {"pillar_name": "Team & Leadership", "score": "67", "weight": "10.00"},
            ],
        },
        "business_health": {"categories": [
            {"category": "Idea & Validation", "risk": "1.0000", "is_flagged": True},
            {"category": "Team & Leadership", "risk": "0.3333", "is_flagged": False},
        ]},
        "top_root_causes": [
            {"label": "Small Sample Bias", "confidence": "0.8500",
             "category": "Idea & Validation", "confirmation_status": "confirmed"},
        ],
        "priority_actions": [
            {"action": "Call five labs and ask for the money.", "priority": 1},
            {"action": "Second raw action.", "priority": 2},
            {"action": "Third raw action.", "priority": 3},
            {"action": "Fourth raw action.", "priority": 4},
            {"action": "Fifth raw action.", "priority": 5},
        ],
        "key_symptoms": [],
        "next_steps": ["Book the calls.", "Read what came back."],
    }


def _doc(narrative, insights, **kw) -> str:
    return build_report_document(narrative, insights, founder_name="Ayush", **kw)


# --- every narrated section reaches the page --------------------------------

def test_every_narrated_section_appears_in_the_document(insights):
    """The sections the generator writes are the sections the founder reads."""
    narrative = _Narrative(sections=(
        _Section("founder_summary", "Founder summary", "You are early and moving."),
        _Section("founder_dna", "Founder DNA", "You build with conviction."),
        _Section("business_dna", "Business DNA", "Validation is the weak pillar."),
        _Section("problem_path", "Root cause", "The pattern is consistent."),
        _Section("supporting_evidence", "What this is based on",
                 "Your own words carried this."),
        _Section("priority_actions", "Priority actions", "Three to confirm, three to solve."),
        _Section("recommended_roadmap", "How to sequence this", "Confirm before you solve."),
        _Section("why_steps", "Why these steps", "Each one tests the same assumption."),
        _Section("discovery_cta", "Your next move with Ally", "Bring this to a session."),
    ))
    html = _doc(narrative, insights)

    for prose in ("You are early and moving.", "You build with conviction.",
                  "Validation is the weak pillar.", "The pattern is consistent.",
                  "Your own words carried this.", "Three to confirm, three to solve.",
                  "Confirm before you solve.", "Each one tests the same assumption.",
                  "Bring this to a session."):
        assert prose in html, f"missing narrated prose: {prose!r}"

    for heading in ("Founder summary", "What this is based on", "How to sequence this",
                    "Why these steps", "Your next move with Ally"):
        assert heading in html, f"missing section heading: {heading!r}"


def test_sections_render_in_the_narratives_own_order(insights):
    """Order is the narrative's, not this module's -- that is what makes the
    variant orderings real on the page."""
    narrative = _Narrative(sections=(
        _Section("founder_dna", "Founder DNA", "DNA prose."),
        _Section("founder_summary", "Founder summary", "Summary prose."),
    ))
    html = _doc(narrative, insights)
    assert html.index("DNA prose.") < html.index("Summary prose.")


def test_blocks_are_numbered_sequentially_with_no_gaps(insights):
    """Numbering follows what actually rendered. Hardcoded 01..07 left holes
    whenever a section was absent."""
    narrative = _Narrative(sections=(
        _Section("founder_summary", "Founder summary", "One."),
        _Section("founder_dna", "Founder DNA", "Two."),
        _Section("discovery_cta", "Your next move with Ally", "Three."),
    ))
    html = _doc(narrative, insights)
    assert '<span class="block-num">01</span>' in html
    assert '<span class="block-num">02</span>' in html
    assert '<span class="block-num">03</span>' in html


# --- variants ----------------------------------------------------------------

def test_no_clear_diagnosis_states_no_root_cause(insights):
    """NO_CLEAR_DIAGNOSIS omits problem_path on purpose. Reading the cause off
    `insights` regardless told a founder whose diagnosis was inconclusive
    exactly what was wrong with their company."""
    narrative = _Narrative(sections=(
        _Section("founder_summary", "Founder summary", "Summary prose."),
        _Section("areas_to_monitor", "Areas to monitor", "Two things to watch."),
    ))
    html = _doc(narrative, insights)

    assert "Small Sample Bias" not in html
    assert "What&rsquo;s in the way looks like" not in html
    assert "Why Ally reached this conclusion" not in html
    # ...and the hero must not promise one either.
    assert "traced what&rsquo;s holding you back" not in html
    assert "No single root cause separated out clearly" in html


def test_distress_leads_with_wellbeing_not_the_business_ring(insights):
    """The distress variant's whole point: this founder is not opened with a
    score ring and a verdict about their company."""
    narrative = _Narrative(sections=(
        _Section("acknowledgement", "Before we begin",
                 "What you are carrying right now matters more than any diagnosis."),
        _Section("support_recommendation", "A first step for you",
                 "Talk to someone this week."),
        _Section("founder_dna", "Founder DNA", "DNA prose."),
        _Section("business_dna", "Business DNA", "Business prose."),
    ))
    html = _doc(narrative, insights)

    assert "What you are carrying right now" in html
    assert "Talk to someone this week." in html
    # No health ring at all, and the wellbeing copy precedes every score.
    assert 'class="ring"' not in html
    assert html.index("What you are carrying right now") < html.index("Business prose.")
    assert html.index("Talk to someone this week.") < html.index('class="bars"')


def test_low_confidence_hedge_precedes_everything(insights):
    narrative = _Narrative(sections=(
        _Section("hedge", "A note on certainty", "This read is provisional."),
        _Section("founder_summary", "Founder summary", "Summary prose."),
        _Section("problem_path", "Root cause", "The pattern is consistent."),
    ))
    html = _doc(narrative, insights)
    assert "This read is provisional." in html
    assert html.index("This read is provisional.") < html.index("Summary prose.")


# --- no raw numbers ----------------------------------------------------------

def test_document_exposes_bands_not_numbers(insights):
    """ReportNarrative.exposes_numeric_scores is False and generator.py's header
    says the report shows bands, not grades. The document printed the pillar
    score, the chip score and the confidence percentage three times over."""
    narrative = _Narrative(sections=(
        _Section("business_dna", "Business DNA", "Business prose."),
        _Section("problem_path", "Root cause", "The pattern is consistent."),
    ))
    html = _doc(narrative, insights)

    assert '<div class="bar-val">20</div>' not in html
    assert '<div class="bar-val">67</div>' not in html
    assert "85% confidence" not in html
    assert "Confidence 85%" not in html
    assert '<span class="conf-num">85%</span>' not in html
    # The band words stand in their place.
    assert "Critical gap" in html or "Developing" in html or "Strong" in html


# --- the 3+3 plan ------------------------------------------------------------

def test_actions_come_from_the_narratives_capped_plan(insights):
    """generator.py caps the founder-facing plan at 3 confirm + 3 solve LINES.
    The document rendered insights["priority_actions"][:5] instead -- a second,
    independent rendering of the same product rule, off the raw pipeline
    output, which could disagree with the prose beside it."""
    narrative = _Narrative(sections=(
        _Section("priority_actions", "Priority actions", "Three then three.", {
            "confirm_actions": [{"next_actions": ["Confirm one.", "Confirm two."], "priority": 1}],
            "solve_actions": [{"next_actions": ["Solve one."], "priority": 2}],
        }),
    ))
    html = _doc(narrative, insights)

    for line in ("Confirm one.", "Confirm two.", "Solve one."):
        assert line in html
    # None of the raw pipeline actions leak in alongside the plan.
    assert "Call five labs and ask for the money." not in html
    assert "Fifth raw action." not in html


def test_actions_fall_back_to_insights_for_an_older_snapshot(insights):
    """A report generated before priority_actions carried facts still shows its
    actions -- narrative_snapshot is cached per report forever."""
    narrative = _Narrative(sections=(_Section("founder_dna", "Founder DNA", "DNA prose."),))
    html = _doc(narrative, insights)
    assert "Call five labs and ask for the money." in html


# --- old snapshots keep their insight-derived blocks -------------------------

def test_older_snapshots_keep_pillars_quotes_and_roadmap(insights):
    """narrative_snapshot is cached forever, so reports written before a section
    existed carry a narrative that has never heard of it. Their insight-derived
    blocks must not vanish with it."""
    narrative = _Narrative(sections=(
        _Section("founder_dna", "Founder DNA", "DNA prose."),
        _Section("problem_path", "Root cause", "The pattern is consistent."),
    ))
    html = _doc(narrative, insights)

    assert 'class="bars"' in html          # pillars, with no business_dna section
    assert "Your next 2 weeks" in html     # roadmap, with no recommended_roadmap section
    assert "Where you stand" in html


# --- facts -------------------------------------------------------------------

def test_founder_dna_facts_are_rendered(insights):
    """The DNA dimensions are facts, not prose; dropping them left the founder's
    archetype, origin and vision off their own report."""
    narrative = _Narrative(sections=(
        _Section("founder_dna", "Founder DNA", "DNA prose.", {
            "archetype": {"name": "The Builder", "core_motivation": "To make it real"},
            "origin": "I started after my father's shop closed.",
            "stress_response": ["Goes quiet", "Works longer"],
        }),
    ))
    html = _doc(narrative, insights)

    assert "The Builder" in html
    assert "I started after my father&#x27;s shop closed." in html
    assert "Goes quiet" in html
    assert "Works longer" in html


def test_facts_are_escaped(insights):
    """Facts carry founder-authored text."""
    narrative = _Narrative(sections=(
        _Section("founder_dna", "Founder DNA", "DNA prose.",
                 {"origin": "<img src=x onerror=alert(1)>"}),
    ))
    html = _doc(narrative, insights)
    assert "<img src=x" not in html
    assert "&lt;img src=x" in html
