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

def _bar(name: str, score: int, sub: str = "") -> str:
    sub_html = f'<span class="bar-weight">{e(sub)}</span>' if sub else ""
    return (
        f'<div class="bar-row {_tone(score)}">'
        f'<div class="bar-name">{e(name)}{sub_html}</div>'
        f'<div class="bar-track"><div class="bar-fill" style="width:{max(score, 0)}%"></div></div>'
        f'<div class="bar-val">{score}</div></div>'
    )


def _chip(name: str, score: int) -> str:
    # A 0 would render as an invisible track, which reads as "no data" rather
    # than "nothing here yet" -- floor the *bar* at 4% while the number stays 0.
    width = max(score, 4)
    return (
        f'<div class="chip-row {_tone(score)}"><span>{e(name)}</span>'
        f'<div class="mini-track"><div class="mini-fill" style="width:{width}%"></div></div>'
        f'<span class="chip-num">{score}</span></div>'
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
          pillars: Sequence[Mapping[str, Any]], confidence: int, when: str,
          with_actions: bool) -> str:
    band = str(health.get("band") or "In progress")
    overall = _num(health.get("overall_score"))
    # The band, not the number. Showing "31/100" to a founder is a grade; the
    # band plus the arc says the same thing without handing them a verdict.
    actions = (
        '<div class="hero-actions">'
        '<button class="btn btn-primary" data-report-action="download">Download PDF</button>'
        '<button class="btn btn-ghost" data-report-action="share">Share</button></div>'
    ) if with_actions else ""
    lede = (f"Ally scanned {len(categories)} business dimensions and {len(pillars)} pillars, "
            f"and traced what&rsquo;s holding you back to one root cause")
    lede += f" &mdash; with {confidence}% confidence." if confidence else "."
    return (
        f'<header class="hero"><div>'
        f'<span class="eyebrow">Founder Clarity Report &middot; {e(when)}</span>'
        f'<h1>{e(name)}, here&rsquo;s what&rsquo;s actually in your way</h1>'
        f'<p>{lede}</p>{actions}</div>{_ring(band, overall)}</header>'
    )


def _care(narrative) -> str:
    """The wellbeing note, when the diagnosis flagged one.

    Deliberately ABOVE section 01 and above every number: a founder in a hard
    stretch is not led with a red score. Everyone gets the report -- this is
    how they get it.
    """
    sec = _section(narrative, "psychological_note")
    if sec is None or not sec.prose:
        return ""
    return (f'<div class="care"><h3>{e(sec.heading)}</h3>{_paras(sec.prose)}</div>')


def _standing(pillars: Sequence[Mapping[str, Any]]) -> str:
    if not pillars:
        return ""
    ranked = sorted(pillars, key=lambda p: _num(p.get("score")))
    bars = "".join(
        _bar(str(p.get("pillar_name") or "Pillar"), _num(p.get("score")),
             f"{_num(p.get('weight'))}% of overall" if p.get("weight") else "")
        for p in ranked
    )
    return _block("02", "Where you stand",
                  "<p>Six pillars, weighted by how much each one decides survival at your "
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
    strengths = [p for p in scored if p[1] >= 50][:4] or scored[:3]
    gaps = [p for p in reversed(scored) if p[1] < 50][:6] or scored[-3:]

    left = "".join(_chip(n, s) for n, s in strengths)
    right = "".join(_chip(n, s) for n, s in gaps)
    return _block(
        "03", "Your high points and low points",
        "<p>Every business dimension we scanned, ranked. The left column is what you can "
        "lean on right now; the right is what will decide the next few months.</p>"
        '<div class="split">'
        '<div class="panel panel-strength"><div class="panel-title"><span class="dot"></span>'
        f'Lean on this</div><div class="chip-list">{left}</div>'
        '<p class="panel-note">These are working. They are the machinery you will use to '
        'fix the column on the right.</p></div>'
        '<div class="panel panel-gap"><div class="panel-title"><span class="dot"></span>'
        f'Fix this first</div><div class="chip-list">{right}</div>'
        '<p class="panel-note">This is where the next two weeks should go.</p></div></div>')


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
                  + (f" Confidence {conf}%." if conf else "")))

    trail = "".join(
        f'<div class="trail-step"><span class="step-num">{i}</span>'
        f'<p><b>{e(title)}</b> &mdash; {e(text)}</p></div>'
        for i, (title, text) in enumerate(steps, start=1)
    )
    cards = "".join(
        f'<div class="cause"><span class="cause-cat">'
        f'{e(c.get("category") or "Pattern")}</span>'
        f'<span class="cause-name">{e(c.get("label") or c.get("name"))}</span>'
        f'<span class="cause-conf">{_pct(c.get("confidence"))}% confidence &middot; '
        f'{"primary" if i == 0 else "supporting"}</span></div>'
        for i, c in enumerate(causes[:3])
    )
    strength = "High" if conf >= 75 else ("Moderate" if conf >= 50 else "Early")
    lead = _paras(sec.prose) if sec is not None and sec.prose else ""

    return _block(
        "04", "Root cause",
        f'<div class="finding"><div class="finding-tag"><span class="dot"></span>'
        f'Ally&rsquo;s finding &middot; {e(strength)} confidence</div>'
        f'<h3>What&rsquo;s in the way looks like <em>{e(label)}</em>.</h3>'
        f'<div class="conf-row"><div class="conf-track">'
        f'<div class="conf-fill" style="width:{conf}%"></div></div>'
        f'<span class="conf-num">{conf}%</span></div></div>'
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
        reading = (entry.get("symptoms") or [None])[0]
        if not evidence or not reading:
            continue
        pair = evidence[0]
        if not isinstance(pair, (list, tuple)) or len(pair) < 2:
            continue
        question, answer = pair[0], pair[1]
        quotes.append(
            f'<div class="quote"><div class="quote-q">{e(question)}</div>'
            f'<div class="quote-a">&ldquo;{e(answer)}&rdquo;</div>'
            f'<div class="quote-read"><b>What this tells us:</b> {e(reading)}</div></div>')
        if len(quotes) == 3:
            break
    if not quotes:
        return ""
    return _block("05", "What we heard",
                  "<p>The reading above comes from what you actually said. These moments "
                  "carried the most weight.</p>" + "".join(quotes))


def _actions(actions: Sequence[Mapping[str, Any]]) -> str:
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
    if not rows:
        return ""
    return _block("06", "Priority actions", "".join(rows))


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
    return _block(
        "07", "Your next 2 weeks",
        "<p>Two weeks, one question to answer. Everything here serves it.</p>"
        f'<div class="road">{"".join(cards)}</div>'
        + (f'<div class="stats">{strip}</div>' if strip else ""))


def _summary(narrative) -> str:
    for key in ("founder_dna", "executive_summary"):
        sec = _section(narrative, key)
        if sec is not None and sec.prose:
            return _block("01", "Founder summary", _paras(sec.prose))
    return ""


# --- the document ------------------------------------------------------------

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
    """
    data: Mapping[str, Any] = insights or {}
    health = data.get("business_health_score") or {}
    pillars = health.get("pillars") or []
    categories = (data.get("business_health") or {}).get("categories") or []
    causes = data.get("top_root_causes") or []
    actions = data.get("priority_actions") or []
    symptoms = data.get("key_symptoms") or []
    steps = [s for s in (data.get("next_steps") or []) if str(s).strip()]

    confidence = _pct(causes[0].get("confidence")) if causes else 0
    name = _first_name(founder_name)
    when = (generated_at or datetime.now()).strftime("%b %Y")
    flagged = sum(1 for c in categories if c.get("is_flagged"))

    stats: list[tuple[str, str]] = []
    if actions:
        stats.append((str(len(actions)), "Actions to start in the next two weeks"))
    if flagged:
        stats.append((str(flagged), "Dimensions needing attention"))
    if confidence:
        stats.append((str(confidence), "Confidence in this diagnosis"))

    body = "".join([
        _hero(name, health, categories, pillars, confidence, when,
              with_actions and not for_print),
        _care(narrative),
        _summary(narrative),
        _standing(pillars),
        _high_low(categories),
        _root_cause(narrative, causes, categories, pillars),
        _heard(symptoms),
        _actions(actions),
        _roadmap(steps, stats),
        '<div class="close"><div><h3>This report is yours to keep.</h3>'
        '<p>Come back and re-run the clarity check once these actions are done '
        '&mdash; that is when these numbers will actually move.</p></div>'
        + ('<button class="btn btn-dark" data-report-action="download">Download PDF</button>'
           if (with_actions and not for_print) else "")
        + '</div>',
        f'<p class="footnote">Generated from your diagnosis on '
        f'{e((generated_at or datetime.now()).strftime("%d %b %Y"))}. Confidence reflects how '
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




