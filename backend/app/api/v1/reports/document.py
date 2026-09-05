"""The founder report as ONE HTML document -- the single source of truth.

Screen and PDF render from this module and nothing else. Before it existed the
report was written twice (a React page and a hand-written print_html), which is
exactly how the PDF drifted from the screen: two implementations of one design,
kept in step by discipline rather than by construction. A founder who downloads
their report must get the document they were just reading, not a lookalike.

So: `build_report_document(...)` emits a complete, self-contained page. The API
serves it to the React shell as-is, and Gotenberg renders the same bytes to PDF.
The only difference between the two is `for_print`, and it is deliberately tiny
-- see document_style.PRINT_ONLY for everything a page of paper changes.

Fonts are base64-embedded rather than linked, so neither surface depends on a
font CDN and the PDF cannot silently render in a fallback face.
"""

from __future__ import annotations

import html
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence

from app.api.v1.reports.document_style import PRINT_ONLY, STYLE, font_face_css

# --- band thresholds ---------------------------------------------------------
# Shared by every bar and chip so a 42 is the same colour wherever it appears.
_CRITICAL_MAX = 35
_WATCH_MAX = 60


def _tone(score: int) -> str:
    if score < _CRITICAL_MAX:
        return "t-critical"
    if score < _WATCH_MAX:
        return "t-watch"
    return "t-ok"


#: Band wording for a score whose real band the narrative did not carry.
#:
#: The report's stated contract is bands, not numbers (see generator.py's
#: header and ReportNarrative.exposes_numeric_scores, which is False): raw
#: pillar scores and confidence percentages are the grade-anxiety surface the
#: diagnosis was designed to avoid. This document printed them anyway -- the
#: bar value, the chip value, and "Confidence 42%" three times over -- so the
#: page and the PDF contradicted the flag the API set on the very same report.
#: Real bands come from readiness_pillars.score_bands via the narrative; these
#: are the fallback for a pillar the narrative did not describe.
_BAND_WORDS = {"t-critical": "Critical gap", "t-watch": "Developing", "t-ok": "Strong"}


def _band_word(score: int) -> str:
    return _BAND_WORDS[_tone(score)]


def _num(value: Any, default: int = 0) -> int:
    """Scores arrive as Decimal, str or int depending on the path that wrote
    them. One coercion point beats a dozen int(float(...)) calls."""
    if value is None:
        return default
    try:
        return int(Decimal(str(value)))
    except (InvalidOperation, ValueError, TypeError):
        return default


def _pct(value: Any, default: int = 0) -> int:
    """A 0..1 ratio as a whole percentage."""
    if value is None:
        return default
    try:
        return int(round(float(Decimal(str(value))) * 100))
    except (InvalidOperation, ValueError, TypeError):
        return default


def e(text: Any) -> str:
    """Escape. Every founder-authored string passes through here -- answers are
    user input and land in both the page and the PDF."""
    return html.escape(str(text if text is not None else ""))


def _first_name(full: str | None) -> str:
    return (full or "").strip().split(" ")[0] or "there"


def _section(narrative, key: str):
    for s in getattr(narrative, "sections", ()):
        if s.key == key:
            return s
    return None


def _facts(narrative, key: str) -> Mapping[str, Any]:
    sec = _section(narrative, key)
    return (sec.facts or {}) if sec is not None else {}


# --- fragment builders -------------------------------------------------------

def _bar(name: str, score: int, sub: str = "", band: str | None = None) -> str:
    """One pillar. The BAR is proportional to the score; the label beside it is
    the band, never the number -- a filled track shows relative standing without
    handing the founder a mark out of 100."""
    sub_html = f'<span class="bar-weight">{e(sub)}</span>' if sub else ""
    return (
        f'<div class="bar-row {_tone(score)}">'
        f'<div class="bar-name">{e(name)}{sub_html}</div>'
        f'<div class="bar-track"><div class="bar-fill" style="width:{max(score, 0)}%"></div></div>'
        f'<div class="bar-val">{e(band or _band_word(score))}</div></div>'
    )


def _chip(name: str, score: int) -> str:
    # A 0 would render as an invisible track, which reads as "no data" rather
    # than "nothing here yet" -- floor the *bar* at 4%.
    width = max(score, 4)
    return (
        f'<div class="chip-row {_tone(score)}"><span>{e(name)}</span>'
        f'<div class="mini-track"><div class="mini-fill" style="width:{width}%"></div></div>'
        f'<span class="chip-num">{e(_band_word(score))}</span></div>'
    )


def _block(num: str, heading: str, body: str) -> str:
    return (
        f'<section class="block"><div class="block-head">'
        f'<span class="block-num">{e(num)}</span><h2>{e(heading)}</h2></div>'
        f'<div class="block-body">{body}</div></section>'
    )


def _paras(prose: str | None) -> str:
    """Narrator prose arrives as plain text with blank-line paragraph breaks."""
    if not prose:
        return ""
    chunks = [c.strip() for c in str(prose).split("\n\n") if c.strip()]
    return "".join(f"<p>{e(c)}</p>" for c in chunks)


def _ring(band: str, score: int) -> str:
    radius, circumference = 80, 502.65
    dash = max(min(score, 100), 0) / 100 * circumference
    stroke = {"t-critical": "#BC5540", "t-watch": "#C2892B"}.get(_tone(score), "#2FBF71")
    return (
        '<div class="ring-wrap"><div class="ring">'
        f'<svg width="186" height="186" viewBox="0 0 186 186" aria-hidden="true">'
        f'<circle cx="93" cy="93" r="{radius}" fill="none" stroke="rgba(255,255,255,.13)" '
        f'stroke-width="11"></circle>'
        f'<circle cx="93" cy="93" r="{radius}" fill="none" stroke="{stroke}" stroke-width="11" '
        f'stroke-linecap="round" stroke-dasharray="{dash:.1f} {circumference}"></circle></svg>'
        f'<div class="ring-face"><div class="ring-band">{e(band)}</div>'
        f'<div class="ring-sub">Business Health</div></div></div>'
        '<div class="ring-note">Where you are today &mdash; not a verdict on whether '
        'this works.</div></div>'
    )


# --- sections ----------------------------------------------------------------

def _hero(name: str, health: Mapping[str, Any], categories: Sequence[Mapping[str, Any]],
          pillars: Sequence[Mapping[str, Any]], when: str, with_actions: bool,
          *, has_root_cause: bool, wellbeing_first: bool) -> str:
    """The title header.

    `wellbeing_first` is the DISTRESS variant's whole point: that founder is not
    opened with a business-health ring and a claim about what is wrong with
    their company. They get their name, the date, and then the acknowledgement
    the variant put first -- the ring and the diagnosis lede are dropped, not
    reordered around.

    `has_root_cause` follows the narrative rather than the raw insights: on
    NO_CLEAR_DIAGNOSIS the generator deliberately omits problem_path, and the
    lede must not promise a root cause the report then does not state.
    """
    band = str(health.get("band") or "In progress")
    overall = _num(health.get("overall_score"))
    # The band, not the number. Showing "31/100" to a founder is a grade; the
    # band plus the arc says the same thing without handing them a verdict.
    actions = (
        '<div class="hero-actions">'
        '<button class="btn btn-primary" data-report-action="download">Download PDF</button>'
        '<button class="btn btn-ghost" data-report-action="share">Share</button></div>'
    ) if with_actions else ""

    if wellbeing_first:
        return (
            f'<header class="hero hero-quiet"><div>'
            f'<span class="eyebrow">Founder Clarity Report &middot; {e(when)}</span>'
            f'<h1>{e(name)}, before anything about the business</h1>'
            f'<p>This one starts with how you are doing, because that comes '
            f'first.</p>{actions}</div></header>'
        )

    headline = (f"{e(name)}, here&rsquo;s what&rsquo;s actually in your way"
                if has_root_cause else f"{e(name)}, here&rsquo;s where you stand")
    lede = f"Ally scanned {len(categories)} business dimensions and {len(pillars)} pillars"
    lede += (", and traced what&rsquo;s holding you back to one root cause."
             if has_root_cause
             else ". No single root cause separated out clearly &mdash; what "
                  "follows is what the scan did show.")
    return (
        f'<header class="hero"><div>'
        f'<span class="eyebrow">Founder Clarity Report &middot; {e(when)}</span>'
        f'<h1>{headline}</h1>'
        f'<p>{lede}</p>{actions}</div>{_ring(band, overall)}</header>'
    )


def _pillar_bands(narrative) -> dict[str, str]:
    """pillar name -> its written band, from the narrative's Business DNA facts.

    The bands are the report's own vocabulary for a score (readiness_pillars.
    score_bands), so preferring them over a threshold guess keeps the page
    saying what the narrative says about the same pillar.
    """
    out: dict[str, str] = {}
    for p in (_facts(narrative, "business_dna").get("pillars") or []):
        if isinstance(p, Mapping):
            name, band = p.get("pillar_name"), p.get("band")
            if name and band:
                out[str(name)] = str(band)
    return out


def _standing(pillars: Sequence[Mapping[str, Any]], bands: Mapping[str, str]) -> str:
    if not pillars:
        return ""
    ranked = sorted(pillars, key=lambda p: _num(p.get("score")))
    bars = "".join(
        _bar(str(p.get("pillar_name") or "Pillar"), _num(p.get("score")),
             f"{_num(p.get('weight'))}% of overall" if p.get("weight") else "",
             band=bands.get(str(p.get("pillar_name") or "")))
        for p in ranked
    )
    return ("<p>Six pillars, weighted by how much each one decides survival at your "
            "stage. Lowest first &mdash; that is also the order to work in.</p>"
            f'<div class="bars">{bars}</div>')


def _high_low(categories: Sequence[Mapping[str, Any]]) -> str:
    """Strengths and gaps, from the same category risks.

    Risk is stored 0..1 where 1 is worst, so strength is its inverse. Showing
    both halves matters: a report that lists only what is broken is a report a
    founder stops opening.
    """
    if not categories:
        return ""
    scored = [(str(c.get("category") or "Dimension"), 100 - _pct(c.get("risk")))
              for c in categories]
    scored.sort(key=lambda pair: pair[1], reverse=True)

    # Split on the SAME boundary the band words use, not on a separate cut.
    # This used to filter at 50, which is not a band edge (_tone breaks at 35
    # and 60), so the two disagreed: a dimension scoring 62 reads "Strong" and
    # was still eligible for the gap column, and when nothing scored under 50
    # the `or scored[-3:]` fallback filled "Fix this first" with the bottom
    # three whatever their band. Live report, 25 Aug: "Fix this first --
    # Team & Leadership: Strong".
    strengths = [p for p in scored if p[1] >= _WATCH_MAX][:4]
    gaps = [p for p in reversed(scored) if p[1] < _WATCH_MAX][:6]

    # Nothing genuinely weak is a real result, and saying so is better than
    # promoting three healthy dimensions into a column headed "Fix this first".
    if not gaps:
        right_body = (
            '<p class="panel-note">Nothing scored below the line this time. The '
            'weakest of the above is where any attention should go, but none of '
            'them is currently a gap.</p>')
    else:
        right_body = (f'<div class="chip-list">{"".join(_chip(n, s) for n, s in gaps)}</div>'
                      '<p class="panel-note">This is where the next two weeks should go.</p>')

    if not strengths:
        left_body = (
            '<p class="panel-note">Nothing has cleared the line yet. That is normal '
            'this early, and it means the column on the right is the whole plan.</p>')
    else:
        left_body = (f'<div class="chip-list">{"".join(_chip(n, s) for n, s in strengths)}</div>'
                     '<p class="panel-note">These are working. They are the machinery you '
                     'will use to fix the column on the right.</p>')

    return (
        "<p>Every business dimension we scanned, ranked. The left column is what you can "
        "lean on right now; the right is what will decide the next few months.</p>"
        '<div class="split">'
        '<div class="panel panel-strength"><div class="panel-title"><span class="dot"></span>'
        f'Lean on this</div>{left_body}</div>'
        '<div class="panel panel-gap"><div class="panel-title"><span class="dot"></span>'
        f'Fix this first</div>{right_body}</div></div>')


def _root_cause(narrative, causes: Sequence[Mapping[str, Any]],
                categories: Sequence[Mapping[str, Any]],
                pillars: Sequence[Mapping[str, Any]]) -> str:
    """The finding, its confidence, and the trail that produced it.

    Intervention IDs never appear here -- a founder has no use for INT-9, and
    showing one is the report admitting it was written for the engine. Labels
    only, everywhere.
    """
    if not causes:
        return ""
    primary = causes[0]
    conf = _pct(primary.get("confidence"))
    label = str(primary.get("label") or primary.get("name") or "the pattern below")
    sec = _section(narrative, "problem_path")
    stated = str(_facts(narrative, "problem_path").get("stated_symptom") or "").strip()
    # Hard rule 5 (generator.py): Not-Tested must never read as certain as
    # Confirmed. The engine carries that categorically on every finding, which
    # is the honest way to say it -- unlike a percentage, which invites the
    # founder to read 62% as a mark rather than as how much evidence there was.
    status = str(primary.get("confirmation_status") or "").replace("_", " ").strip()

    strongest = sorted(pillars, key=lambda p: _num(p.get("score")), reverse=True)[:3]
    worst_cat = max(categories, key=lambda c: _pct(c.get("risk")), default=None)

    steps: list[tuple[str, str]] = []
    if stated:
        # The founder's own framing, trimmed -- their words open the trail.
        steps.append(("What you described", stated[:240].rstrip() +
                      ("…" if len(stated) > 240 else "")))
    if strongest:
        names = ", ".join(str(p.get("pillar_name")) for p in strongest)
        steps.append(("What Ally ruled out",
                      f"{names} all scored higher. This is not a discipline or "
                      f"capability gap."))
    if worst_cat is not None:
        steps.append(("The signal",
                      f"{worst_cat.get('category')} carried the heaviest risk of every "
                      f"dimension we scanned."))
    if len(causes) > 1:
        steps.append(("The link to you",
                      "The same pattern showed up across answers that were not about "
                      "the same topic."))
    steps.append(("The conclusion",
                  f"One mechanism explains the rest: {label}."
                  + (f" Status: {status}." if status else "")))

    trail = "".join(
        f'<div class="trail-step"><span class="step-num">{i}</span>'
        f'<p><b>{e(title)}</b> &mdash; {e(text)}</p></div>'
        for i, (title, text) in enumerate(steps, start=1)
    )
    cards = "".join(
        f'<div class="cause"><span class="cause-cat">'
        f'{e(c.get("category") or "Pattern")}</span>'
        f'<span class="cause-name">{e(c.get("label") or c.get("name"))}</span>'
        f'<span class="cause-conf">'
        f'{e(str(c.get("confirmation_status") or "").replace("_", " ") or "not tested")}'
        f' &middot; {"primary" if i == 0 else "supporting"}</span></div>'
        for i, c in enumerate(causes[:3])
    )
    strength = "High" if conf >= 75 else ("Moderate" if conf >= 50 else "Early")
    lead = _paras(sec.prose) if sec is not None and sec.prose else ""

    return (
        f'<div class="finding"><div class="finding-tag"><span class="dot"></span>'
        f'Ally&rsquo;s finding &middot; {e(strength)} confidence</div>'
        f'<h3>What&rsquo;s in the way looks like <em>{e(label)}</em>.</h3>'
        # The bar stays (it shows how settled the read is at a glance); the
        # number beside it does not.
        f'<div class="conf-row"><div class="conf-track">'
        f'<div class="conf-fill" style="width:{conf}%"></div></div>'
        f'<span class="conf-num">{e(strength)}</span></div></div>'
        f'{lead}'
        f'<div class="trail"><div class="trail-head">Why Ally reached this conclusion</div>'
        f'{trail}</div>'
        + (f'<p>Patterns supporting this read:</p><div class="cause-grid">{cards}</div>'
           if cards else ""))


def _heard(symptoms: Sequence[Mapping[str, Any]]) -> str:
    """What the founder said, paired with what it meant.

    The quote is evidence, never the finding. Every one is followed by the
    interpretation it produced -- a report that only replays your own answers
    back at you has told you nothing.
    """
    quotes: list[str] = []
    for entry in symptoms:
        evidence = entry.get("evidence") or []
        pattern = str((entry.get("symptoms") or [""])[0] or "").strip()
        category = str(entry.get("category") or "").strip()
        if not evidence or not pattern:
            continue
        pair = evidence[0]
        if not isinstance(pair, (list, tuple)) or len(pair) < 2:
            continue
        question, answer = pair[0], pair[1]

        # `symptoms` is generic catalogue text describing the PATTERN for this
        # CATEGORY -- schemas.SymptomHighlight says so itself: "written before
        # this founder existed". It is not a reading of the single answer above
        # it, and presenting it as one produced visible non-sequiturs in the
        # live PDF: "unresolved tension among team members? / yes / What this
        # tells us: No board, advisory board, or formal mentorship structure in
        # place." Label it for what it is -- the pattern this answer counted
        # toward -- so the page stops asserting a link it cannot support.
        cat_html = (f'<span class="quote-cat">{e(category)}</span>' if category else "")
        quotes.append(
            f'<div class="quote">{cat_html}<div class="quote-q">{e(question)}</div>'
            f'<div class="quote-a">&ldquo;{e(answer)}&rdquo;</div>'
            f'<div class="quote-read"><b>The pattern this counted toward:</b> '
            f'{e(pattern)}</div></div>')
        if len(quotes) == 3:
            break
    if not quotes:
        return ""
    return ("<p>The reading above comes from what you actually said. These moments "
            "carried the most weight.</p>" + "".join(quotes))


def _plan_lines(narrative) -> tuple[list[str], list[str]]:
    """The narrative's 3+3 plan as (confirm lines, solve lines).

    The free tier's plan is "3 lines to confirm/isolate, 3 lines to solve", and
    generator.py applies that cap carefully -- to the flattened LINES, because
    one intervention can carry five steps. Reading the plan back off the
    narrative keeps ONE source of truth for it. The document used to render
    insights["priority_actions"][:5] instead: a second, independent rendering
    of the same product rule, off the raw pipeline output, which could and did
    disagree with the plan the prose beside it described.
    """
    facts = _facts(narrative, "priority_actions")

    def lines(key: str) -> list[str]:
        out: list[str] = []
        for entry in (facts.get(key) or []):
            if not isinstance(entry, Mapping):
                continue
            for step in (entry.get("next_actions") or []):
                text = str(step).strip()
                if text:
                    out.append(text)
        return out

    return lines("confirm_actions"), lines("solve_actions")


def _action_rows(items: Sequence[str], start: int, impact: str, tag_class: str) -> str:
    return "".join(
        f'<div class="action"><span class="action-num">{i}</span>'
        f'<div class="action-body"><div class="action-text">{e(text)}</div>'
        f'<div class="action-meta">'
        f'<span class="tag {tag_class}">{impact}</span></div></div></div>'
        for i, text in enumerate(items, start=start)
    )


#: How many lines get the numbered, full-weight treatment.
STEPS_SHOWN = 3

#: Of those, how many are drawn from the confirm half. The remainder comes from
#: the solve half, so a founder always leaves with at least one line that
#: CHANGES something rather than three that only measure. When one half is
#: empty this degrades to taking all three from whichever half has lines --
#: which is today's reality while ACTION_PLAN_BALANCE_LLM is off and the
#: library produces confirm lines only.
_CONFIRM_IN_STEPS = 2


def _three_steps(
    confirm: Sequence[str], solve: Sequence[str]
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Split the plan into the three numbered steps and the follow-on lines.

    Viraj's 26 Aug review of the report structure asked for "3 clear steps,
    1 2 3". The framework doc's s6 still defines the free tier as 3 confirm +
    3 solve, so both hold: three steps carry the page, and the rest become the
    "once those come back" list underneath rather than being dropped.

    Returns (headline, rest) as (line, kind) pairs where kind is Confirm/Solve.
    """
    tagged = [(line, "Confirm") for line in confirm] + [(line, "Solve") for line in solve]
    if not tagged:
        return [], []

    picked: list[tuple[str, str]] = []
    picked += [(line, "Confirm") for line in confirm[:_CONFIRM_IN_STEPS]]
    picked += [(line, "Solve") for line in solve[:STEPS_SHOWN - len(picked)]]
    # One half empty -- top up from whatever is left rather than showing two.
    if len(picked) < STEPS_SHOWN:
        picked += [p for p in tagged if p not in picked][:STEPS_SHOWN - len(picked)]

    rest = [p for p in tagged if p not in picked]
    return picked[:STEPS_SHOWN], rest


def _step_rows(steps: Sequence[tuple[str, str]]) -> str:
    return "".join(
        f'<div class="action"><span class="action-num">{i}</span>'
        f'<div class="action-body"><div class="action-text">{e(text)}</div>'
        f'<div class="action-meta"><span class="tag '
        f'{"tag-high" if kind == "Confirm" else "tag-med"}">{e(kind)}</span>'
        f'</div></div></div>'
        for i, (text, kind) in enumerate(steps, start=1)
    )


def _actions(narrative, actions: Sequence[Mapping[str, Any]]) -> str:
    """Priority actions, preferring the narrative's capped 3+3 plan.

    Falls back to the raw pipeline actions only when the narrative carries no
    plan at all (an older report whose snapshot predates the section), so a
    report that has one never shows a different list beside the prose
    describing it.
    """
    confirm, solve = _plan_lines(narrative)
    if confirm or solve:
        headline, rest = _three_steps(confirm, solve)
        parts = [_step_rows(headline)]
        if rest:
            rows = "".join(f"<li>{e(line)}</li>" for line, _kind in rest)
            parts.append(
                '<div class="then"><p class="action-group">Once those come back:</p>'
                f'<ol class="then-list">{rows}</ol></div>')
        return "".join(parts)

    if not actions:
        return ""
    rows: list[str] = []
    for i, a in enumerate(actions[:5], start=1):
        text = str(a.get("action") or "").strip()
        if not text:
            continue
        priority = _num(a.get("priority"), default=i)
        impact = "High impact" if priority <= 2 else "Medium impact"
        tag_class = "tag-high" if priority <= 2 else "tag-med"
        # The label, never the intervention_id.
        label = str(a.get("intervention_label") or "").strip()
        link = (f'<span class="tag tag-link">Addresses &middot; {e(label)}</span>'
                if label else "")
        rows.append(
            f'<div class="action"><span class="action-num">{i}</span>'
            f'<div class="action-body"><div class="action-text">{e(text)}</div>'
            f'<div class="action-meta">'
            f'<span class="tag {tag_class}">{impact}</span>{link}</div></div></div>')
    return "".join(rows)


# Two weeks, in the two moves a fortnight actually has: do the thing, then read
# what came back. Deliberately not a month and emphatically not a quarter -- a
# 90-day plan handed to a founder at the ideation stage is built on assumptions
# the first week is supposed to test, and by week three it is describing a
# business that may not exist. Two weeks is close enough that the founder can
# still picture it, and short enough that the report stays honest about how
# little it can know past the next test.
_ROAD_STAGES = (
    ("Week 1", "First moves"),
    ("Week 2", "Read the signal"),
)


def _roadmap(steps: Sequence[str], stats: Sequence[tuple[str, str]]) -> str:
    if not steps:
        return ""
    # ceil, capped at 2 cards x 3 lines. Six actions is already more than most
    # people start in a fortnight; a longer list reads as a backlog, not a plan.
    per = max(1, -(-min(len(steps), 6) // len(_ROAD_STAGES)))
    cards: list[str] = []
    for idx, (when, title) in enumerate(_ROAD_STAGES):
        chunk = list(steps)[idx * per:(idx + 1) * per]
        if not chunk:
            continue
        items = "".join(f"<li>{e(s)}</li>" for s in chunk)
        cards.append(
            f'<div class="road-card"><span class="road-when">{e(when)}</span>'
            f'<h3>{e(title)}</h3><ul class="road-list">{items}</ul></div>')
    if not cards:
        return ""
    strip = "".join(
        f'<div class="stat"><span class="stat-num">{e(num)}</span>'
        f'<span class="stat-label">{e(label)}</span></div>'
        for num, label in stats
    ) if stats else ""
    return ("<p>Two weeks, one question to answer. Everything here serves it.</p>"
            f'<div class="road">{"".join(cards)}</div>'
            + (f'<div class="stats">{strip}</div>' if strip else ""))


# --- generic narrative rendering ---------------------------------------------

def _fact_value(value: Any) -> str:
    """One fact's value as readable HTML.

    Facts are engine-owned and open-ended -- a string, a list of answers, or a
    small dict like the archetype. Rendering them generically is what lets a
    dimension the founder only answered last week appear without this module
    knowing its name.
    """
    if isinstance(value, Mapping):
        parts = [f"{e(str(k).replace('_', ' ').title())}: {e(v)}"
                 for k, v in value.items()
                 if not isinstance(v, (list, dict)) and v not in (None, "", True, False)]
        return " &middot; ".join(parts)
    if isinstance(value, (list, tuple)):
        items = [e(v) for v in value if isinstance(v, (str, int, float)) and str(v).strip()]
        if not items:
            return ""
        return '<ul class="fact-list">' + "".join(f"<li>{v}</li>" for v in items) + "</ul>"
    return e(value)


def _facts_html(facts: Mapping[str, Any], skip: Sequence[str] = ()) -> str:
    """Founder-facing facts as labelled rows. Internal keys are already stripped
    upstream by generator._founder_facts; this only shapes what is left."""
    rows: list[str] = []
    for key, value in (facts or {}).items():
        # A bool is an internal switch, never founder-facing prose. Without this
        # the CTA section's own flag rendered as a labelled row reading
        # "Cta / True" on the last page of the live PDF -- `True` is not caught
        # by the empty-value check below, and bool is a subclass of int so it
        # would otherwise fall through to the number formatting.
        if isinstance(value, bool):
            continue
        if key in skip or value in (None, "", [], {}):
            continue
        rendered = _fact_value(value)
        if not rendered:
            continue
        label = str(key).replace("_", " ").strip().title()
        rows.append(f'<div class="fact"><span class="fact-k">{e(label)}</span>'
                    f'<div class="fact-v">{rendered}</div></div>')
    return f'<div class="facts">{"".join(rows)}</div>' if rows else ""


def _callout(narrative, key: str) -> str:
    """A lead-in section, rendered above the numbered body and above every
    number.

    These are the sections a founder must read BEFORE the business content, and
    the variant machinery exists to put them there: DISTRESS leads with
    acknowledgement + support_recommendation, LOW_CONFIDENCE opens with the
    hedge, and the wellbeing note is deliberately placed above section 01. None
    of them were rendered by this document at all -- a founder in distress was
    led with a business-health ring and a root-cause verdict, which is the exact
    thing the distress variant exists to prevent.
    """
    sec = _section(narrative, key)
    if sec is None or not sec.prose:
        return ""
    return f'<div class="care"><h3>{e(sec.heading)}</h3>{_paras(sec.prose)}</div>'


#: Sections rendered as un-numbered callouts ABOVE the numbered body, in the
#: order the narrative put them. Everything else becomes a numbered block.
#:
#: psychological_note deliberately is NOT here. The approved report structure
#: (Viraj, 26 Aug) numbers it and places it after Founder DNA, so it reads as
#: part of the report rather than as a preamble. It keeps its early position
#: because the narrative's own section order puts it there -- this module does
#: not reorder sections, it only decides numbered vs callout.
#:
#: The DISTRESS lead-ins stay callouts: acknowledgement and
#: support_recommendation exist precisely to reach a founder BEFORE any
#: business content or numbering, and `wellbeing_first` still drops the health
#: ring for them.
_LEAD_SECTIONS = ("acknowledgement", "support_recommendation", "hedge")

#: Blocks whose CONTENT comes from `insights` rather than from narrator prose,
#: paired with the heading to use when the narrative has no section to host
#: them. narrative_snapshot is cached per report forever, so reports generated
#: before a section existed carry a narrative that has never heard of it --
#: gating these purely on the narrative would silently strip the pillar bars,
#: the quotes and the two-week plan off every report written before those
#: sections shipped. The data is right there in insights; render it.
#:
#: problem_path is deliberately NOT in this list. Its absence is a real signal
#: rather than an old snapshot: NO_CLEAR_DIAGNOSIS omits it on purpose, and
#: rendering a root cause anyway -- which is what reading top_root_causes
#: straight off insights did -- told a founder whose diagnosis was inconclusive
#: exactly what was wrong with their company.
_ORPHAN_BLOCKS = (
    ("business_dna", "Where you stand"),
    ("supporting_evidence", "What we heard"),
    ("priority_actions", "Priority actions"),
    ("recommended_roadmap", "Your next 2 weeks"),
)

#: Facts already spoken by a section's own visual treatment, so rendering them
#: again as label/value rows would just repeat the block above them.
_FACTS_SKIP = {
    "business_dna": ("pillars", "overall_band"),
    "problem_path": ("root_causes", "stated_symptom", "symptom_probes"),
    "priority_actions": ("confirm_actions", "solve_actions", "intervention_ids"),
    "supporting_evidence": ("probes", "root_causes"),
    "recommended_roadmap": ("confirm_steps", "solve_steps"),
}


def _section_body(key: str, narrative, ctx: Mapping[str, Any]) -> str:
    """The body of one numbered section: its prose, plus whatever visual
    treatment that section has.

    Driven by the narrative's OWN section list, which is what makes the variant
    rules real on the page. Previously this document consulted exactly three
    narrative keys and derived everything else straight from `insights`, so:
    every other section the generator wrote (the evidence trail, the sequencing,
    why those steps, areas to monitor, the CTA, and the founder's DNA facts) was
    silently dropped from the page, the share link and the PDF; and the root
    cause rendered even on variants that deliberately omit it, because the raw
    insights still carried one.
    """
    sec = _section(narrative, key)
    prose = _paras(sec.prose) if sec is not None and sec.prose else ""
    facts = (sec.facts or {}) if sec is not None else {}
    extra = ""

    if key == "psychological_note":
        # Numbered now (see _LEAD_SECTIONS) but it keeps the `care` treatment:
        # this is the one section that must not read like another business
        # block, and test_wellbeing_note_precedes_every_score pins that it
        # still lands ahead of any score. The heading is drawn by _block, so
        # only the prose is wrapped here.
        return f'<div class="care">{prose}</div>' if prose else ""
    if key == "business_dna":
        extra = _standing(ctx["pillars"], ctx["bands"]) + _high_low(ctx["categories"])
    elif key == "problem_path":
        # The narrative's prose is rendered INSIDE _root_cause (it leads the
        # trail), so it must not be prepended here too. When there is no cause
        # to build the finding from, _root_cause yields nothing and the prose
        # would go with it -- fall back to the prose alone rather than dropping
        # a section the narrator actually wrote.
        return _root_cause(narrative, ctx["causes"], ctx["categories"], ctx["pillars"]) or prose
    elif key == "supporting_evidence":
        extra = _heard(ctx["symptoms"])
    elif key == "priority_actions":
        extra = _actions(narrative, ctx["actions"])
    elif key == "recommended_roadmap":
        extra = _roadmap(ctx["steps"], ctx["stats"])

    body = prose + extra + _facts_html(facts, skip=_FACTS_SKIP.get(key, ()))
    return body


# --- the document ------------------------------------------------------------

def _unpopulated_note(narrative) -> str:
    """Name any section this report did not get, rather than silently omitting it.

    The generator already decides to leave a section out when it has nothing
    real to put there -- expected_impact is the usual one -- and records which.
    The React fallback view printed that list; this document, which is what a
    founder actually reads on screen and in the PDF, did not. So the honesty was
    written and then not delivered to anybody.

    Worded as a deliberate omission, because that is what it is: a founder who
    sees a section named and empty should understand we chose not to invent it,
    not wonder whether their report failed halfway.
    """
    names = tuple(getattr(narrative, "unpopulated_sections", ()) or ())
    if not names:
        return ""
    readable = ", ".join(n.replace("_", " ") for n in names)
    return (
        '<p class="footnote">Not included in this report: '
        f'{e(readable)}. Ally leaves a section out when it does not have enough '
        'to say something true there, rather than filling it in.</p>'
    )


def build_report_document(
    narrative,
    insights: Mapping[str, Any] | None,
    *,
    founder_name: str | None = None,
    generated_at: datetime | None = None,
    for_print: bool = False,
    with_actions: bool = True,
) -> str:
    """The founder's report as one complete HTML document.

    `for_print` is the ONLY branch between the founder's screen and their PDF,
    and it does nothing but drop the two buttons and add paged-media rules --
    see document_style.PRINT_ONLY. Everything else is the same bytes, which is
    what makes "the PDF looks like the screen" a property of the code rather
    than a promise somebody has to keep.

    `with_actions` is separate and orthogonal: it exists for the PUBLIC shared
    view, where Download and Share are controls the visitor cannot use (both hit
    endpoints that require the founder's own session). It does not touch layout,
    so the parity invariant above is unaffected -- printing still implies no
    actions, and the test that pins screen-vs-print compares the default.

    Renders whatever the report actually has: every section returns "" when its
    data is missing, so a thin report degrades to a shorter document instead of
    a broken one. A founder always gets a report.

    Section ORDER and section PRESENCE both come from the narrative, not from
    this module. That is what makes the report variants real for the founder
    rather than only for the API: DISTRESS leads with the acknowledgement and
    drops the hero ring, LOW_CONFIDENCE opens with the hedge, and
    NO_CLEAR_DIAGNOSIS states no root cause because the generator wrote no
    problem_path section for it to state.
    """
    data: Mapping[str, Any] = insights or {}
    health = data.get("business_health_score") or {}
    pillars = health.get("pillars") or []
    categories = (data.get("business_health") or {}).get("categories") or []
    causes = data.get("top_root_causes") or []
    actions = data.get("priority_actions") or []
    symptoms = data.get("key_symptoms") or []
    steps = [s for s in (data.get("next_steps") or []) if str(s).strip()]

    name = _first_name(founder_name)
    when = (generated_at or datetime.now()).strftime("%b %Y")
    flagged = sum(1 for c in categories if c.get("is_flagged"))

    keys = [s.key for s in getattr(narrative, "sections", ()) if getattr(s, "key", None)]
    has_root_cause = "problem_path" in keys
    wellbeing_first = "acknowledgement" in keys or "support_recommendation" in keys

    confirm_lines, solve_lines = _plan_lines(narrative)
    planned = len(confirm_lines) + len(solve_lines) or len(actions)

    stats: list[tuple[str, str]] = []
    if planned:
        stats.append((str(planned), "Actions to start in the next two weeks"))
    if flagged:
        stats.append((str(flagged), "Dimensions needing attention"))

    ctx = {
        "pillars": pillars, "categories": categories, "causes": causes,
        "actions": actions, "symptoms": symptoms, "steps": steps, "stats": stats,
        "bands": _pillar_bands(narrative),
    }

    lead = "".join(_callout(narrative, k) for k in keys if k in _LEAD_SECTIONS)

    blocks: list[str] = []
    number = 0
    for key in keys:
        if key in _LEAD_SECTIONS:
            continue
        section_body = _section_body(key, narrative, ctx)
        if not section_body:
            continue
        number += 1
        sec = _section(narrative, key)
        heading = (sec.heading if sec is not None and sec.heading else key.replace("_", " ").title())
        blocks.append(_block(f"{number:02d}", heading, section_body))

    # Insight-derived blocks the narrative had no section for -- see
    # _ORPHAN_BLOCKS. Appended after the narrated ones, in a fixed order.
    for key, heading in _ORPHAN_BLOCKS:
        if key in keys:
            continue
        section_body = _section_body(key, narrative, ctx)
        if not section_body:
            continue
        number += 1
        blocks.append(_block(f"{number:02d}", heading, section_body))

    body = "".join([
        _hero(name, health, categories, pillars, when,
              with_actions and not for_print,
              has_root_cause=has_root_cause, wellbeing_first=wellbeing_first),
        lead,
        "".join(blocks),
        # Was "Come back and re-run the clarity check once these actions are
        # done". There is one diagnosis per account on every plan, so the report
        # was inviting founders to do the one thing the product refuses -- and
        # then they arrive at support asking why they cannot. Re-running at a
        # stage change is intended but unbuilt; until it exists, the closing
        # line points at the surfaces that DO keep moving.
        '<div class="close"><div><h3>This report is yours to keep.</h3>'
        '<p>Work through the actions above in Next steps &mdash; that is where '
        'this picture actually moves. Ally knows what is in this report, so you '
        'can talk any of it through whenever you want.</p></div>'
        + ('<button class="btn btn-dark" data-report-action="download">Download PDF</button>'
           if (with_actions and not for_print) else "")
        + '</div>',
        _unpopulated_note(narrative),
        f'<p class="footnote">Generated from your diagnosis on '
        f'{e((generated_at or datetime.now()).strftime("%d %b %Y"))}. Bands reflect how '
        f'much evidence supported this read &mdash; not how well you are doing.</p>',
    ])

    style = font_face_css() + STYLE + (PRINT_ONLY if for_print else "")
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>Clarity report &middot; {e(name)}</title>'
        f'<style>{style}</style></head>'
        f'<body class="rp"><div class="shell">{body}</div></body></html>'
    )


def build_report_fragment(narrative, insights, **kwargs) -> str:
    """The same document without the html/head wrapper, for mounting inside the
    React shell. Same fragment the PDF is built from -- only the envelope
    differs, so the two cannot drift."""
    full = build_report_document(narrative, insights, **kwargs)
    start = full.index("<body")
    inner = full[full.index(">", start) + 1:full.rindex("</body>")]
    style = full[full.index("<style>"):full.index("</style>") + len("</style>")]
    return f'{style}<div class="rp">{inner}</div>'




