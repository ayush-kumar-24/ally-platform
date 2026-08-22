"""The report document: one builder, three surfaces.

The point of app/api/v1/reports/document.py is that the founder's screen, their
PDF and a shared link cannot drift apart, because there is only one
implementation. That is a property worth pinning: the previous design mirrored
the same look in two codebases and they diverged, which is what these tests
exist to stop happening again.

`_body` strips the <head> before comparing, since the stylesheet is the one part
that legitimately differs (paged-media rules on the print variant).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping

import pytest

from app.api.v1.reports.document import build_report_document

_DOWNLOAD_BTN = ('<button class="btn btn-primary" data-report-action="download">'
                 'Download PDF</button>')
_SHARE_BTN = '<button class="btn btn-ghost" data-report-action="share">Share</button>'
_HERO_ACTIONS = f'<div class="hero-actions">{_DOWNLOAD_BTN}{_SHARE_BTN}</div>'
_CLOSE_BTN = ('<button class="btn btn-dark" data-report-action="download">'
              'Download PDF</button>')


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
def narrative() -> _Narrative:
    return _Narrative(sections=(
        _Section("psychological_note", "Before the business — how you're doing",
                 "This has been a hard stretch, and that matters."),
        _Section("founder_dna", "Founder DNA", "You build with conviction."),
        _Section("problem_path", "Root cause", "The pattern is consistent.",
                 {"stated_symptom": "I keep putting off the one call that would settle it."}),
    ))


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
             "category": "Idea & Validation"},
            {"label": "Fear of Ambiguity", "confidence": "0.8500",
             "category": "Idea & Validation"},
        ],
        "priority_actions": [
            {"action": "Call five labs and ask for the money.", "priority": 1,
             "intervention_label": "Small Sample Bias"},
        ],
        "key_symptoms": [
            {"category": "Idea & Validation",
             "evidence": [["Has anyone else told you this problem is real?",
                           "Honestly, no. It scares me a bit to find out."]],
             "symptoms": ["Built entirely on founder assumptions without external validation"]},
        ],
        "next_steps": ["Call five labs.", "Tag last month's decisions.",
                       "Log each decision and its outcome."],
    }


def _doc(narrative, insights, **kwargs) -> str:
    return build_report_document(
        narrative, insights, founder_name="Priya Nair",
        generated_at=datetime(2026, 8, 21), **kwargs)


def _body(html: str) -> str:
    """Everything after <body> — the markup, without the stylesheet."""
    return html[html.index("<body"):]


# --- the parity guarantee ----------------------------------------------------

def test_print_body_is_identical_to_screen_apart_from_the_buttons(narrative, insights):
    """The whole reason this module exists.

    If this fails, the PDF has started to differ from the page a founder read,
    and the difference is something other than the controls paper cannot carry.
    """
    screen = _body(_doc(narrative, insights))
    printed = _body(_doc(narrative, insights, for_print=True))

    assert printed == screen.replace(_HERO_ACTIONS, "").replace(_CLOSE_BTN, "")


def test_shared_body_is_identical_to_print_body(narrative, insights):
    shared = _body(_doc(narrative, insights, with_actions=False))
    printed = _body(_doc(narrative, insights, for_print=True))
    assert shared == printed


def test_print_variant_removes_buttons_rather_than_hiding_them(narrative, insights):
    """display:none would still ship a Download button into the PDF's markup."""
    printed = _doc(narrative, insights, for_print=True)
    assert "<button" not in printed
    assert 'data-report-action' not in printed


def test_print_variant_carries_paged_media_rules(narrative, insights):
    printed = _doc(narrative, insights, for_print=True)
    assert "@page{size:A4" in printed
    # A root-cause card split across two sheets reads as two half-findings.
    assert "break-inside:avoid" in printed


def test_screen_variant_has_no_page_rules_and_keeps_its_buttons(narrative, insights):
    screen = _doc(narrative, insights)
    assert "@page" not in screen
    assert screen.count("<button") == 3


# --- self-containment (Gotenberg renders with no network) --------------------

def test_document_references_no_external_urls(narrative, insights):
    """A linked font would fall back silently and ship the PDF in the wrong face."""
    for html in (_doc(narrative, insights), _doc(narrative, insights, for_print=True)):
        assert "http://" not in html
        assert "https://" not in html
    assert "data:font/woff2;base64" in _doc(narrative, insights)


# --- what the founder must never see -----------------------------------------

def test_interventions_are_named_never_numbered(narrative, insights):
    html = _doc(narrative, insights)
    assert "Small Sample Bias" in html
    assert "INT-" not in html
    assert "intervention_id" not in html


def test_internal_routing_keys_never_reach_the_page(narrative, insights):
    html = _doc(narrative, insights)
    for internal in ("Section H", "founder_readiness_critical_gap",
                     "psychology_flagged", "_narrator", "red_flag_note"):
        assert internal not in html


def test_overall_score_is_shown_as_a_band_not_a_number(narrative, insights):
    """Bands, not raw numbers: "31/100" hands a founder a grade."""
    html = _doc(narrative, insights)
    assert "Critical Gap" in html
    assert "31/100" not in html
    assert ">31<" not in html          # never as the ring's own figure


def test_founder_answers_are_escaped(narrative, insights):
    """Answers are user input and land in the page, the PDF and a public link."""
    insights["key_symptoms"][0]["evidence"][0][1] = '<img src=x onerror="alert(1)">'
    html = _doc(narrative, insights)
    assert "<img src=x" not in html
    assert "&lt;img src=x" in html


# --- content shape -----------------------------------------------------------

def test_roadmap_covers_two_weeks_not_a_month(narrative, insights):
    html = _doc(narrative, insights)
    assert "Your next 2 weeks" in html
    assert "Week 1" in html and "Week 2" in html
    for beyond in ("Weeks 3", "30–60 days", "60–90 days", "next 30 days"):
        assert beyond not in html


def test_wellbeing_note_precedes_every_score(narrative, insights):
    """A founder in a hard stretch is not led with a red number."""
    html = _doc(narrative, insights)
    assert html.index('class="care"') < html.index('class="bars"')


def test_a_thin_report_degrades_to_a_shorter_document(narrative):
    """Everyone gets a report. Missing data drops sections, never the page."""
    html = _doc(narrative, {})
    assert "<body" in html and "</html>" in html
    assert "Priya" in html
    assert 'class="bars"' not in html      # no pillars to draw
    assert 'class="road"' not in html      # no steps to plan


def test_missing_insights_entirely_still_renders(narrative):
    assert "</html>" in _doc(narrative, None)


# --- share links must always resolve -----------------------------------------

def test_share_url_uses_the_site_origin_when_configured(monkeypatch):
    from app.api.v1.reports import routes
    from app.core.config import settings

    monkeypatch.setattr(settings, "PUBLIC_APP_URL", "https://goxlally.ai/")
    url = routes.share_url_for("tok123", _FakeRequest("https://api.goxlally.ai/"))
    assert url == "https://goxlally.ai/r/tok123"


def test_share_url_falls_back_to_a_path_this_api_actually_serves(monkeypatch):
    """`/r/<token>` is a Vercel rewrite, not a backend route.

    With PUBLIC_APP_URL unset the pretty path would be built against the API
    host, where it 404s -- so the fallback must be the endpoint this service
    really exposes, even though it is uglier.
    """
    from app.api.v1.reports import routes
    from app.core.config import settings

    monkeypatch.setattr(settings, "PUBLIC_APP_URL", "")
    url = routes.share_url_for("tok123", _FakeRequest("https://api.goxlally.ai/"))
    assert url == "https://api.goxlally.ai/api/v1/reports/shared/tok123/view"
    assert "/r/tok123" not in url


class _FakeRequest:
    """Enough of a Request for share_url_for: an origin and the real app, whose
    route table the fallback reverses the path out of."""

    def __init__(self, base_url: str):
        from app.main import app
        self.base_url = base_url
        self.app = app
