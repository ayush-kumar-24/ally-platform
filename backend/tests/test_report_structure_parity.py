"""The report structure Viraj signed off on 26 Aug, and the defects it fixed.

Three of these pin bugs that were visible in a real founder's PDF generated
from production on 25 Aug (clarityreport3.pdf):

  * the last page ended with a labelled row reading "Cta / True";
  * "Fix this first" listed a dimension the same page called Strong;
  * a quote about team conflict was captioned with a conclusion about board
    structure, as though it were a reading of that answer.

The fourth pins the structure itself: three numbered steps carry the page, and
whatever the plan holds beyond them follows underneath rather than vanishing.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.api.v1.reports.document import (
    STEPS_SHOWN,
    _facts_html,
    _heard,
    _high_low,
    _three_steps,
    build_report_document,
)


def _sec(key, heading="H", prose="Prose.", facts=None):
    return SimpleNamespace(key=key, heading=heading, prose=prose, facts=facts or {})


def _narr(*sections):
    return SimpleNamespace(sections=tuple(sections))


# --- "Cta / True" -------------------------------------------------------------

def test_a_boolean_fact_is_never_printed_to_the_founder():
    """THE REGRESSION: page 12 of the live PDF read "Cta" / "True"."""
    html = _facts_html({"cta": True, "booking_enabled": False})
    assert "True" not in html and "False" not in html
    assert html == ""


def test_real_facts_still_render_beside_a_boolean():
    html = _facts_html({"cta": True, "archetype": "Problem Solver"})
    assert "Problem Solver" in html
    assert "True" not in html


# --- "Fix this first: ... Strong" ---------------------------------------------

def _cats(*pairs):
    # risk is 0..1 where 1 is worst; the document scores strength as its inverse
    return [{"category": name, "risk": (100 - score) / 100} for name, score in pairs]


def test_a_healthy_dimension_is_never_listed_under_fix_this_first():
    """THE REGRESSION: every dimension scored above the line, and the fallback
    promoted the bottom three into the gap column anyway -- one of them
    labelled Strong on the same page."""
    html = _high_low(_cats(("Competitive Awareness", 88), ("Idea & Validation", 84),
                           ("Founder Psychology", 79), ("Risk Identification", 72),
                           ("Team & Leadership", 66), ("Operations & Systems", 63)))

    gap_panel = html.split("Fix this first")[1]
    assert "Strong" not in gap_panel
    assert "Nothing scored below the line" in gap_panel


def test_a_real_gap_still_reaches_the_gap_column():
    html = _high_low(_cats(("Market Clarity", 81), ("Operations & Systems", 41)))
    gap_panel = html.split("Fix this first")[1]
    assert "Operations &amp; Systems" in gap_panel
    assert "next two weeks" in gap_panel


def test_the_split_uses_the_same_boundary_as_the_band_words():
    """A dimension at 55 reads "Developing", so it belongs in the gap column.
    The old cut at 50 called it a strength while the chip beside it disagreed."""
    html = _high_low(_cats(("Steady Thing", 78), ("Middling Thing", 55)))
    assert "Middling Thing" in html.split("Fix this first")[1]


def test_nothing_strong_yet_is_said_rather_than_faked():
    html = _high_low(_cats(("Market Clarity", 30), ("Revenue Maturity", 22)))
    lean_panel = html.split("Fix this first")[0]
    assert "Nothing has cleared the line yet" in lean_panel


# --- the mismatched quote caption ---------------------------------------------

def test_catalogue_text_is_not_captioned_as_a_reading_of_one_answer():
    """THE REGRESSION: `symptoms` is generic text about the CATEGORY -- schemas
    calls it "written before this founder existed" -- and it was printed as
    "What this tells us" directly under a single quote."""
    html = _heard([{
        "category": "Team & Leadership",
        "symptoms": ["No board, advisory board, or formal mentorship structure in place"],
        "evidence": [("Is there any unresolved tension among team members?", "yes")],
    }])

    assert "What this tells us" not in html
    assert "The pattern this counted toward" in html
    assert "Team &amp; Leadership" in html
    assert "unresolved tension" in html


def test_a_highlight_without_evidence_is_skipped_rather_than_guessed():
    assert _heard([{"category": "X", "symptoms": ["A pattern."], "evidence": []}]) == ""


# --- three numbered steps -----------------------------------------------------

def test_three_steps_lead_with_confirm_but_always_include_a_solve():
    confirm = ["Count them.", "Ask them.", "Track it."]
    solve = ["Hand one over.", "Set the rule.", "Block a day."]
    steps, rest = _three_steps(confirm, solve)

    assert len(steps) == STEPS_SHOWN
    assert [k for _t, k in steps] == ["Confirm", "Confirm", "Solve"]
    assert steps[2][0] == "Hand one over."
    assert len(rest) == 3, "nothing from the plan is dropped"


def test_a_confirm_only_plan_still_produces_three_steps():
    """Today's live shape while ACTION_PLAN_BALANCE_LLM is off: the library
    types every recommendation the same way, so solve comes back empty."""
    steps, rest = _three_steps(["One.", "Two.", "Three."], [])
    assert len(steps) == STEPS_SHOWN
    assert all(kind == "Confirm" for _t, kind in steps)
    assert rest == []


def test_a_short_plan_shows_what_it_has():
    steps, rest = _three_steps(["Only this."], [])
    assert steps == [("Only this.", "Confirm")]
    assert rest == []


def test_an_empty_plan_produces_nothing():
    assert _three_steps([], []) == ([], [])


@pytest.mark.parametrize("confirm,solve", [
    (["a", "b", "c"], ["d", "e", "f"]),
    (["a", "b", "c", "d"], []),
    ([], ["a", "b", "c", "d"]),
])
def test_every_plan_line_appears_exactly_once(confirm, solve):
    steps, rest = _three_steps(confirm, solve)
    seen = [t for t, _k in steps] + [t for t, _k in rest]
    assert sorted(seen) == sorted(confirm + solve)
    assert len(seen) == len(set(seen))


# --- the psychological note ---------------------------------------------------

def test_the_psychological_note_is_numbered_but_keeps_its_treatment():
    """Numbered per the approved structure, and still rendered as the care
    block so it does not read as another business section."""
    html = build_report_document(
        _narr(_sec("psychological_note", "Before the business", "You are carrying this alone."),
              _sec("business_dna", "Business DNA", "Where you stand.")),
        {"business_health_score": {"band": "Developing", "pillars": []}},
        founder_name="Meera Raghavan",
    )

    assert 'class="care"' in html
    assert "01" in html, "it takes a section number now"
    assert html.index('class="care"') < html.index("Business DNA")
