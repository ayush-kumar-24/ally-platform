"""Print-layout HTML for the founder report -> Gotenberg (headless Chromium) -> PDF.

This is a SELF-CONTAINED HTML document: fonts are base64-embedded and all CSS is
inline, so Gotenberg needs no network and the PDF cannot render with the wrong
font (Phase 0 decision). It is NOT the React component reused server-side -- it
mirrors the same DESIGN LANGUAGE (the tokens: forest palette, Montserrat/Inter/
Fraunces, band cards) and the same sections the engine returns, so screen and PDF
read as one system without pixel-identical markup.

Input is the same ReportNarrative that build_report_pdf took, so the section
order, distress suppression of the CTA, and bands-not-numbers all come for free.
"""

from __future__ import annotations

import base64
import html
from functools import lru_cache
from pathlib import Path

_FONT_DIR = Path(__file__).parent / "assets" / "fonts"

# Band -> accent colour class (mirrors the screen's fd-cat-* treatment).
_BAND_CLASS = {
    "Critical Gap": "band-red",
    "Needs Attention": "band-amber",
    "Developing": "band-amber",
    "Strong": "band-green",
}


@lru_cache(maxsize=1)
def _font_face_css() -> str:
    def face(family: str, style: str, filename: str) -> str:
        data = base64.b64encode((_FONT_DIR / filename).read_bytes()).decode()
        return (
            f"@font-face{{font-family:'{family}';font-style:{style};font-weight:100 900;"
            f"font-display:swap;src:url(data:font/woff2;base64,{data}) format('woff2');}}"
        )

    return "".join([
        face("Inter", "normal", "inter-normal.woff2"),
        face("Inter", "italic", "inter-italic.woff2"),
        face("Montserrat", "normal", "montserrat-normal.woff2"),
        face("Fraunces", "normal", "fraunces-normal.woff2"),
        face("Fraunces", "italic", "fraunces-italic.woff2"),
    ])


# Design tokens (mirror of frontend/src/styles/tokens.css) + paged-media rules.
_STYLE = """
:root{
  --forest:#1B4332;--forest-deep:#0E2A1C;--forest-night:#06140d;
  --emerald:#10B981;--emerald-bright:#34d399;--lime-edge:#A8D94A;
  --ivory:#f7f1eb;--ink:#16241c;--on-dark:#eaf3ee;--on-dark-muted:#a7c0b4;
  --bd:rgba(255,255,255,.13);--card:rgba(255,255,255,.04);
  --red:#f0736a;--amber:#e6b95c;--green:#34d399;
  --display:'Montserrat','Inter',system-ui,sans-serif;
  --body:'Inter',system-ui,sans-serif;--serif:'Fraunces','Georgia',serif;
}
@page{size:A4;margin:16mm 14mm;}
*,*::before,*::after{box-sizing:border-box;-webkit-print-color-adjust:exact;print-color-adjust:exact;}
html,body{margin:0;padding:0;}
body{font-family:var(--body);color:var(--on-dark);background:var(--forest-night);
  font-size:11pt;line-height:1.5;-webkit-font-smoothing:antialiased;}
.wrap{padding:4mm 0;}
.hero{background:linear-gradient(135deg,var(--forest) 0%,var(--forest-deep) 60%,var(--forest-night) 100%);
  border:1px solid var(--bd);border-radius:14px;padding:22px 24px;margin-bottom:22px;
  display:flex;justify-content:space-between;align-items:center;gap:20px;break-inside:avoid;}
.hero-kicker{font-family:var(--body);font-size:8.5pt;letter-spacing:.14em;text-transform:uppercase;
  color:var(--on-dark-muted);margin-bottom:8px;}
.hero-title{font-family:var(--serif);font-style:italic;font-weight:500;font-size:23pt;
  line-height:1.1;margin:0 0 10px;color:#fff;}
.hero-desc{font-size:11pt;color:var(--on-dark-muted);max-width:135mm;margin:0;}
.band-chip{flex:0 0 auto;text-align:center;border:1px solid var(--bd);border-radius:12px;
  padding:14px 16px;background:var(--card);min-width:34mm;}
.band-chip b{display:block;font-family:var(--display);font-size:12.5pt;color:var(--emerald-bright);}
.band-chip span{display:block;font-size:8pt;letter-spacing:.08em;text-transform:uppercase;
  color:var(--on-dark-muted);margin-top:4px;}
.sec-head{display:flex;align-items:baseline;gap:10px;margin:22px 0 8px;break-after:avoid;}
.sec-head .num{font-family:var(--display);font-size:9pt;color:var(--lime-edge);
  border:1px solid var(--bd);border-radius:6px;padding:2px 7px;}
.sec-head h3{font-family:var(--display);font-weight:700;font-size:13.5pt;margin:0;color:#fff;}
.prose{color:var(--on-dark);margin:0 0 6px;max-width:165mm;}
.intro{color:var(--on-dark-muted);}
.card{border:1px solid var(--bd);border-radius:12px;background:var(--card);padding:14px 16px;
  margin-bottom:10px;break-inside:avoid;}
.card em{font-family:var(--serif);font-style:italic;color:var(--emerald-bright);}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;}
.pillar{border-left:3px solid var(--bd);}
.pillar.band-red{border-left-color:var(--red);}
.pillar.band-amber{border-left-color:var(--amber);}
.pillar.band-green{border-left-color:var(--green);}
.pillar-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:5px;}
.pillar-name{font-family:var(--display);font-weight:600;font-size:11pt;color:#fff;}
.pillar-band{font-size:8.5pt;letter-spacing:.03em;text-transform:uppercase;color:var(--on-dark-muted);}
.pillar.band-red .pillar-band{color:var(--red);}
.pillar.band-green .pillar-band{color:var(--green);}
.pillar-desc{font-size:9.5pt;color:var(--on-dark-muted);margin:0;}
.finding{border-left:3px solid var(--emerald);}
.finding .kicker{font-size:8.5pt;letter-spacing:.1em;text-transform:uppercase;
  color:var(--emerald-bright);margin-bottom:6px;}
.finding h4{font-family:var(--serif);font-weight:500;font-size:13pt;line-height:1.4;margin:0;color:#fff;}
.action{display:flex;gap:12px;align-items:flex-start;}
.action .n{flex:0 0 auto;width:22px;height:22px;border-radius:50%;background:var(--emerald);
  color:var(--forest-night);font-family:var(--display);font-weight:700;font-size:10pt;
  display:flex;align-items:center;justify-content:center;}
.action .t{margin:0;color:var(--on-dark);}
.action .tag{font-size:8pt;letter-spacing:.05em;text-transform:uppercase;color:var(--lime-edge);}
.cta{background:linear-gradient(135deg,var(--forest) 0%,var(--forest-deep) 100%);
  border:1px solid var(--bd);border-radius:12px;padding:18px 20px;break-inside:avoid;}
.cta h4{font-family:var(--display);font-weight:700;font-size:13pt;margin:0 0 6px;color:#fff;}
.cta p{margin:0;color:var(--on-dark-muted);}
"""


def _esc(text: str | None) -> str:
    return html.escape(text or "")


def _p(prose: str | None, cls: str = "prose") -> str:
    return f'<p class="{cls}">{_esc(prose)}</p>' if prose else ""


def _sec_head(num: int, heading: str) -> str:
    return (f'<div class="sec-head"><span class="num">{num:02d}</span>'
            f'<h3>{_esc(heading)}</h3></div>')


# Founder DNA dimension key -> printable label, for whichever of the newer
# dimensions actually resolved (see app/api/v1/reasoning/engines/
# founder_dna_extras.py). A dimension with no key present in `facts` simply
# has no card -- never a placeholder "not yet available" card.
_DNA_LABELS = {
    "origin": "Deepest Why",
    "vision": "Vision",
    "strengths_blind_spots": "Strengths &amp; Blind Spots",
    "stress_response": "Stress Response Pattern",
    "communication_preference": "Communication Preference",
    # Phase-2 dimensions (app/api/v1/founder_dna/) -- same dict, same
    # generic render-what's-there loop below, no separate code path needed.
    "purpose_mission": "Purpose &amp; Mission",
    "core_values": "Core Values &amp; Non-Negotiables",
    "mindset_excellence": "Mindset &amp; Excellence Standard",
    "energy_patterns": "Energy Patterns",
    "decision_style": "Decision Style",
    "focus_attention": "Focus, Attention &amp; Response Patterns",
    # Now asked directly rather than derived from the blind_spots /
    # behaviour_patterns catalogues, which held nothing for the
    # psychology-range root causes most founders score.
    "core_motivation": "Core Motivation Driver",
    "strengths_blind_spots": "Strengths &amp; Blind Spots",
    "stress_response": "Stress Response Pattern",
    "communication_preference": "Communication Preference",
    "emotional_intelligence": "Emotional Intelligence",
}


def _founder_dna_cards(facts: dict) -> str:
    """Grid of Founder DNA cards -- archetype plus however many of the newer
    dimensions are present. Mirrors `_pillars()`'s "render what's there"
    approach rather than assuming a fixed set of dimensions."""
    facts = facts or {}
    cells = []
    a = facts.get("archetype") or {}
    if a.get("name"):
        name = _esc(a["name"]) + (" &middot; working hypothesis" if a.get("tentative") else "")
        motiv = f'<p class="pillar-desc">Driven by {_esc(a["core_motivation"])}</p>' if a.get("core_motivation") else ""
        cells.append(f'<div class="card"><div class="pillar-name">{name}</div>{motiv}</div>')
    for key, label in _DNA_LABELS.items():
        value = facts.get(key)
        if not value:
            continue
        desc = "<br>".join(_esc(v) for v in value) if isinstance(value, list) else _esc(value)
        cells.append(
            f'<div class="card"><div class="pillar-name">{label}</div>'
            f'<p class="pillar-desc">{desc}</p></div>'
        )
    return f'<div class="grid">{"".join(cells)}</div>' if cells else ""


def _pillars(facts: dict) -> str:
    cells = []
    for p in (facts or {}).get("pillars") or []:
        band = p.get("band") or ""
        cls = _BAND_CLASS.get(band, "")
        desc = f'<p class="pillar-desc">{_esc(p.get("band_description"))}</p>' if p.get("band_description") else ""
        cells.append(
            f'<div class="card pillar {cls}"><div class="pillar-top">'
            f'<span class="pillar-name">{_esc(p.get("pillar_name"))}</span>'
            f'<span class="pillar-band">{_esc(band)}</span></div>{desc}</div>'
        )
    return f'<div class="grid">{"".join(cells)}</div>' if cells else ""


def _actions(facts: dict) -> str:
    items = []
    for group, tag in (("confirm_actions", "Confirm first"), ("solve_actions", "Start solving")):
        for a in (facts or {}).get(group) or []:
            for step in a.get("next_actions") or []:
                items.append((step, tag))
    rows = "".join(
        f'<div class="card action"><div class="n">{i + 1}</div><div>'
        f'<p class="t">{_esc(step)}</p><span class="tag">{_esc(tag)}</span></div></div>'
        for i, (step, tag) in enumerate(items)
    )
    return rows


def build_report_html(narrative) -> str:
    """Render a ReportNarrative to a self-contained print HTML document."""
    sections = list(narrative.sections)
    by_key = {s.key: s for s in sections}

    overall_band = (by_key.get("business_dna").facts.get("overall_band")
                    if by_key.get("business_dna") else None)

    # Hero: title + business-health band chip (no raw number).
    summary = by_key.get("founder_summary")
    hero_desc = _esc(summary.prose) if summary else ""
    band_chip = (f'<div class="band-chip"><b>{_esc(overall_band)}</b><span>Business health</span></div>'
                 if overall_band else "")
    parts = [
        '<div class="wrap">',
        f'<div class="hero"><div><div class="hero-kicker">Founder DNA Report</div>'
        f'<h1 class="hero-title">Your clarity report</h1>'
        f'<p class="hero-desc">{hero_desc}</p></div>{band_chip}</div>',
    ]

    num = 0
    for s in sections:
        if s.key == "founder_summary":
            num += 1
            parts.append(_sec_head(num, "Founder summary") + _p(s.prose, "prose"))
        elif s.key == "founder_dna":
            num += 1
            parts.append(_sec_head(num, "Founder DNA") + _p(s.prose, "prose intro")
                         + _founder_dna_cards(s.facts))
        elif s.key == "psychological_note":
            num += 1
            parts.append(_sec_head(num, s.heading) + _p(s.prose, "prose intro"))
        elif s.key == "business_dna":
            num += 1
            parts.append(_sec_head(num, "Business DNA") + _p(s.prose, "prose intro")
                         + _pillars(s.facts))
        elif s.key == "problem_path":
            num += 1
            parts.append(_sec_head(num, "Root cause")
                         + f'<div class="card finding"><div class="kicker">Ally&rsquo;s finding</div>'
                           f'<h4>{_esc(s.prose)}</h4></div>')
        elif s.key == "areas_to_monitor":
            num += 1
            parts.append(_sec_head(num, "Areas to monitor") + _p(s.prose, "prose intro"))
        elif s.key == "priority_actions":
            rows = _actions(s.facts)
            if rows:
                num += 1
                parts.append(_sec_head(num, "Priority actions") + _p(s.prose, "prose intro") + rows)
        elif s.key in ("acknowledgement", "support_recommendation", "hedge"):
            num += 1
            parts.append(_sec_head(num, s.heading) + _p(s.prose, "prose"))
        elif s.key == "discovery_cta":
            num += 1
            parts.append(_sec_head(num, s.heading)
                         + f'<div class="cta"><h4>Turn this diagnosis into a plan.</h4>'
                           f'<p>{_esc(s.prose)}</p></div>')
        else:
            num += 1
            parts.append(_sec_head(num, s.heading) + _p(s.prose, "prose"))

    parts.append("</div>")
    body = "".join(parts)
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        f"<style>{_font_face_css()}{_STYLE}</style></head><body>{body}</body></html>"
    )
