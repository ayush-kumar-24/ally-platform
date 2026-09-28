"""No internal vocabulary in a rendered report.

A user told us the reports were hard to understand. Most of the hard words were
not the model's: they were hardcoded sentences, title-cased fact keys, and
stored band descriptions, which the model then repeated because those were the
words it was handed.

This test is what stops them growing back one sentence at a time. It renders a
full report and fails on any BANNED term in the report's OWN text.

WHAT IT DELIBERATELY DOES NOT CHECK. The founder's own quoted answers. A
founder may well write "our runway" or "the root cause is me", and censoring
their words back to them would be worse than the jargon. So the fixture's
quotes are checked out, and everything the report says in its own voice is
checked in.
"""

from __future__ import annotations

import datetime
import html
import re

from app.api.v1.reports.document import build_report_document
from app.api.v1.reports.generator import ReportNarrativeGenerator
from app.api.v1.reports.payload import (
    ActionItem, ArchetypeFinding, PillarFinding, ReportPayload, RootCauseFinding,
)
from app.api.v1.reports.plain_words import BANNED

_BANDS = {
    "Critical Gap": "The team is dysfunctional or non-existent.",
    "Needs Attention": "There is drive but there are signs of strain.",
}


def _pillar(name, score, band):
    return PillarFinding(pillar_id=0, name=name, score=score, band=band,
                         band_description=_BANDS[band], red_flag_triggered=(score <= 35),
                         red_flag_note=None)


#: A report with every jargon-carrying section switched on: red flags, an
#: unconfirmed root cause, confirm actions, band descriptions, the works.
def _report_html():
    pillars = (
        _pillar("Team & Leadership", 20, "Critical Gap"),
        _pillar("Revenue Maturity", 30, "Critical Gap"),
        _pillar("Founder Readiness", 45, "Needs Attention"),
        _pillar("Market Clarity", 50, "Needs Attention"),
    )
    payload = ReportPayload(
        report_id=1, founder_id=1, session_id=1, founder_name="Test",
        tone_code="T", tone_persona="Auditor", session_state="stable",
        distress_acknowledged_first=False, overall_confidence_score=62.0,
        business_health_overall=31, business_health_band="Critical Gap",
        pillars=pillars,
        red_flag_pillars=tuple(p for p in pillars if p.red_flag_triggered),
        archetype=ArchetypeFinding("Operator", "ARCH-002", "Mastery", True, 0.7),
        top_root_causes=(
            RootCauseFinding(1, "Lack of Trust", "Operations & Systems",
                             "unconfirmed", True, 1),
            RootCauseFinding(2, "Small Sample Bias", "Idea & Validation",
                             "unconfirmed", True, 2),
        ),
        confirm_actions=(
            ActionItem(1, 1, ("Ask five customers what they would pay.",), ""),
        ),
        solve_actions=(),
        category_risk_scores={"Operations & Systems": 0.62, "Go-To-Market": 0.2},
        stated_symptom="I do not know what to charge.",
        symptom_probes=(("What have you tried?", "Nothing yet."),),
        diagnosis_answers=20, distress_evidence=0,
    )
    narrative = ReportNarrativeGenerator().generate(payload)
    cats = [
        {"category": "Operations & Systems", "risk": 0.62, "answers_count": 5,
         "red_count": 3, "is_flagged": True},
        {"category": "Go-To-Market", "risk": 0.2, "answers_count": 4,
         "red_count": 0, "is_flagged": False},
    ]
    insights = {
        "business_health_score": {
            "overall_score": 31, "band": "Critical Gap",
            "pillars": [{"pillar_name": p.name, "score": p.score, "band": p.band,
                         "weight": 25, "red_flag_triggered": p.red_flag_triggered}
                        for p in pillars]},
        "business_health": {"categories": cats},
        "top_root_causes": [{"name": rc.name, "category": rc.category,
                             "confirmation_status": rc.confirmation_status,
                             "rank": rc.rank, "confidence": 0.4}
                            for rc in payload.top_root_causes],
        "priority_actions": [{"next_actions": ["Ask five customers what they would pay."]}],
        "key_symptoms": [], "next_steps": [],
    }
    return build_report_document(narrative, insights, founder_name="Test",
                                 generated_at=datetime.datetime(2026, 9, 28))


def _report_own_words(page: str) -> str:
    """The report's text, with the founder's quoted answers removed.

    Quotes are wrapped in the typographic quotes the document emits
    (&ldquo;/&rdquo;), so they can be cut precisely rather than guessed at.
    """
    text = re.sub(r"<style.*?</style>", " ", page, flags=re.S)
    text = re.sub(r"<script.*?</script>", " ", text, flags=re.S)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    return re.sub(r"“.*?”", " ", text, flags=re.S).lower()


def test_no_internal_vocabulary_reaches_the_founder():
    own_words = _report_own_words(_report_html())
    found = sorted({term for term in BANNED if term in own_words})
    assert not found, (
        "the report used internal vocabulary in its own voice: "
        + ", ".join(found)
        + " -- see reports/plain_words.py for what to say instead"
    )


def test_the_guard_would_actually_catch_something():
    """A test that can only pass is not a guard. If BANNED ever empties, or the
    stripping above ever eats the whole page, this fails."""
    assert BANNED
    own_words = _report_own_words(_report_html())
    assert len(own_words) > 2000, "the report text was stripped away, not checked"
    assert "pillar" in " ".join(BANNED)


def test_the_bands_read_in_plain_words():
    page = _report_own_words(_report_html())
    assert "not working yet" in page
    assert "needs work" in page
    assert "critical gap" not in page


def test_a_founders_own_words_are_never_censored():
    """The exclusion is real: a quote containing a banned word stays on the
    page, it is only excluded from what this test polices."""
    page = _report_html()
    assert "I do not know what to charge." in page


# --- a card that cannot say anything is not printed --------------------------

def _dna_facts(**payload_kw):
    from app.api.v1.reports.generator import ReportNarrativeGenerator
    payload = ReportPayload(
        report_id=1, founder_id=1, session_id=1, founder_name="Test",
        tone_code="T", tone_persona="Auditor", session_state="stable",
        distress_acknowledged_first=False, overall_confidence_score=62.0,
        business_health_overall=31, business_health_band="Critical Gap",
        pillars=(), red_flag_pillars=(), archetype=None, top_root_causes=(),
        confirm_actions=(), solve_actions=(),
        founder_origin="2013.",
        phase2_dimensions={
            "core_values": ("A sales manager gave 9% away without asking.",),
            "emotional_intelligence": ("Our Halol plant head, Ramesh, 2022.",),
            "focus_attention": ("Monday.",),
        },
        **payload_kw,
    )
    slots, facts = ReportNarrativeGenerator()._slots_and_facts(
        "founder_dna", payload, False)
    return facts


def test_a_dimension_with_no_read_is_not_given_a_card():
    """EMOTIONAL INTELLIGENCE over "Our Halol plant head, Ramesh, 2022" is what
    this drops: the answer names a moment without describing it, so there is
    nothing to say about the founder from it."""
    facts = _dna_facts(
        reads_attempted=True,
        dimension_reads={"core_values": "You mind more about the promise."},
    )
    assert "core_values" in facts
    assert "emotional_intelligence" not in facts
    assert "focus_attention" not in facts
    assert "origin" not in facts, "origin is a card too, and 2013. is not a read"


def test_a_report_from_before_reads_keeps_every_card():
    """Gated on reads_attempted, so an old report does not silently lose most
    of its Founder DNA section."""
    facts = _dna_facts(reads_attempted=False, dimension_reads={})
    for key in ("core_values", "emotional_intelligence", "focus_attention", "origin"):
        assert key in facts


def test_the_read_leads_the_card_and_the_answers_back_it_up():
    from app.api.v1.reports.document import _facts_html

    html = _facts_html({
        "core_values": ["A sales manager gave 9% away without asking."],
        "_reads": {"core_values": "You mind more about the promise than the quarter."},
        "_questions": {"core_values": ["Tell me about a line someone crossed."]},
    })
    assert "You mind more about the promise than the quarter." in html
    assert "In your words" in html
    assert "A sales manager gave 9% away without asking." in html
    # The read comes first: it is what the heading promises.
    assert html.index("You mind more") < html.index("In your words")
