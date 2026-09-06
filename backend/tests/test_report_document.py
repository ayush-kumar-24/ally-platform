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

def test_share_url_ignores_public_app_url(monkeypatch):
    """THE REGRESSION GUARD. PUBLIC_APP_URL must never shape a share link.

    This test used to assert the opposite, and that is exactly how sharing
    broke. PUBLIC_APP_URL is set to the MARKETING site (goxlally.ai) rather than
    the app, so `<PUBLIC_APP_URL>/r/<token>` sent every recipient to a 404 page
    on a static site.

    The `/r/` rewrite itself was never the problem -- it lives in vercel.json and
    works, verified against production. The host was wrong, not the path.

    PUBLIC_APP_URL still has a real job (bouncing a founder back to /app/plan
    after the calendar OAuth redirect, where the same wrong value is a separate
    live bug). It just has nothing to do with shares.
    """
    from app.api.v1.reports import routes
    from app.core.config import settings

    monkeypatch.setattr(settings, "PUBLIC_APP_URL", "https://goxlally.ai/")
    monkeypatch.setattr(settings, "SHARE_LINK_BASE_URL", "")
    monkeypatch.setattr(settings, "PUBLIC_API_URL", "")
    url = routes.share_url_for("tok123", _FakeRequest("https://api.goxlally.ai/"))
    assert url == "https://api.goxlally.ai/api/v1/reports/shared/tok123/view"
    assert "/r/tok123" not in url


def test_share_url_defaults_to_a_path_this_api_actually_serves(monkeypatch):
    """With nothing configured, the link must still resolve.

    The default is the endpoint this service really exposes -- longer than
    `/r/<token>`, and it works with no CDN rewrite, no second domain and no
    configuration at all.
    """
    from app.api.v1.reports import routes
    from app.core.config import settings

    monkeypatch.setattr(settings, "PUBLIC_APP_URL", "")
    monkeypatch.setattr(settings, "SHARE_LINK_BASE_URL", "")
    monkeypatch.setattr(settings, "PUBLIC_API_URL", "")
    url = routes.share_url_for("tok123", _FakeRequest("https://api.goxlally.ai/"))
    assert url == "https://api.goxlally.ai/api/v1/reports/shared/tok123/view"


def test_share_url_prefers_public_api_url_over_the_request_origin(monkeypatch):
    """Behind a proxy that rewrites Host, the request's own origin is wrong.

    PUBLIC_API_URL is how the API is told its real public address, so a link
    built inside it points somewhere a visitor can actually reach.
    """
    from app.api.v1.reports import routes
    from app.core.config import settings

    monkeypatch.setattr(settings, "PUBLIC_APP_URL", "")
    monkeypatch.setattr(settings, "SHARE_LINK_BASE_URL", "")
    monkeypatch.setattr(settings, "PUBLIC_API_URL", "https://app.goxlally.ai/")
    url = routes.share_url_for("tok123", _FakeRequest("http://10.0.1.7:8000/"))
    assert url == "https://app.goxlally.ai/api/v1/reports/shared/tok123/view"


def test_share_url_uses_the_pretty_path_only_when_opted_into(monkeypatch):
    """SHARE_LINK_BASE_URL is opt-in, and means "a rewrite really exists here".

    In production this should be https://app.goxlally.ai, where the vercel.json
    /r/:token rewrite is live and verified. It is opt-in rather than inferred
    because pointing it at an origin WITHOUT that rewrite produces links that
    look perfect and 404 -- exactly the failure this whole change is undoing.
    """
    from app.api.v1.reports import routes
    from app.core.config import settings

    monkeypatch.setattr(settings, "PUBLIC_APP_URL", "")
    monkeypatch.setattr(settings, "PUBLIC_API_URL", "")
    monkeypatch.setattr(settings, "SHARE_LINK_BASE_URL", "https://app.goxlally.ai/")
    url = routes.share_url_for("tok123", _FakeRequest("https://api.goxlally.ai/"))
    assert url == "https://app.goxlally.ai/r/tok123"


class _FakeRequest:
    """Enough of a Request for share_url_for: an origin and the real app, whose
    route table the fallback reverses the path out of."""

    def __init__(self, base_url: str):
        from app.main import app
        self.base_url = base_url
        self.app = app


def test_the_vercel_rewrite_still_points_at_the_route_this_api_serves():
    """The pretty share link and the backend route must not drift apart.

    `/r/<token>` is a rewrite in frontend/vercel.json; the path it forwards to
    is a route in this app. Nothing else compares them, and the failure is
    invisible: remount the reports router and the fallback test above goes red,
    someone updates its expected string, ships -- and the rewrite still names
    the old path. The fallback link keeps working, so nothing is red anywhere.
    The only symptom is the URL a founder actually forwards going back to 404ing.

    Yes, this is a backend test reading a frontend file. That is deliberate:
    vercel.json is deployed by Vercel and can import nothing from Python, so
    this is the only place the two halves can be checked against each other.

    Skipped, not failed, when the file is absent -- the backend image is built
    from backend/ alone, and a missing frontend directory there is normal. A
    vercel.json that EXISTS and is wrong always fails.
    """
    import json
    from pathlib import Path

    from app.main import app

    vercel = Path(__file__).resolve().parents[2] / "frontend" / "vercel.json"
    if not vercel.is_file():
        pytest.skip("frontend/vercel.json not in this checkout (backend-only build context)")

    rewrites = json.loads(vercel.read_text(encoding="utf-8")).get("rewrites", [])
    # An explicit lookup rather than next(...): a bare StopIteration when the
    # rule has been deleted says nothing about what broke or why it matters.
    matching = [r for r in rewrites if r.get("source") == "/r/:token"]
    assert matching, (
        "frontend/vercel.json no longer rewrites /r/:token — every share link "
        "built from PUBLIC_APP_URL will 404."
    )

    # The same call share_url_for uses, so this follows a remount instead of
    # hardcoding the prefix a second time.
    served = app.url_path_for("shared_report_page", token=":token")
    destination = matching[0].get("destination", "")
    assert destination.endswith(served), (
        f"vercel.json rewrites /r/:token to {destination!r}, but this API serves "
        f"{served!r}. The share link a founder forwards will 404 while the "
        f"fallback link keeps working, so nothing else will go red."
    )
