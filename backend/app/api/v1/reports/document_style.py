"""Stylesheet for the founder report document.

Kept in its own module so the CSS is one uninterrupted block that can be diffed
against the approved design without Python interleaved through it. Imported by
document.py; nothing else should read it.

A single committed visual world (forest + paper), deliberately NOT theme-
reactive: this is a branded document, and the PDF a founder forwards to an
investor must look like the screen they approved. Every colour is painted
explicitly so the page holds on any host background.
"""

from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

_FONT_DIR = Path(__file__).parent / "assets" / "fonts"


@lru_cache(maxsize=1)
def font_face_css() -> str:
    """Every face base64-embedded into the document.

    Linked webfonts were never an option here: Gotenberg renders with no
    network of its own, so a linked face would silently fall back and the PDF
    would ship in the wrong typeface with nothing to signal it. Embedding costs
    bytes once and makes the failure impossible.
    """
    def face(family: str, style: str, filename: str) -> str:
        data = base64.b64encode((_FONT_DIR / filename).read_bytes()).decode()
        return (
            f"@font-face{{font-family:'{family}';font-style:{style};font-weight:100 900;"
            f"font-display:swap;src:url(data:font/woff2;base64,{data}) format('woff2');}}"
        )

    return "".join([
        face("Inter", "normal", "inter-normal.woff2"),
        face("Inter", "italic", "inter-italic.woff2"),
        face("Fraunces", "normal", "fraunces-normal.woff2"),
        face("Fraunces", "italic", "fraunces-italic.woff2"),
    ])


# Ported verbatim from the approved design.
STYLE = """
:root{
  --forest-900:#0E2A1B; --forest-800:#12351F; --forest-700:#1B4332; --forest-500:#2D6A4F;
  --paper:#F7F4EE; --paper-card:#FFFDFA; --paper-line:#E2DCD0;
  --ink:#17241C; --ink-soft:#4A5A50; --ink-faint:#7C8A81;
  --signal:#2FBF71; --signal-lit:#4ADE80; --amber:#C2892B; --rust:#BC5540;
  --display:'Fraunces','Iowan Old Style',Georgia,serif;
  --body:'Inter',system-ui,-apple-system,'Segoe UI',sans-serif;
  --measure:63ch; --shell:1080px;
}
.rp *{box-sizing:border-box;}
.rp{background:var(--paper);color:var(--ink);font-family:var(--body);
  font-size:16.5px;line-height:1.62;-webkit-font-smoothing:antialiased;}
.rp .shell{max-width:var(--shell);margin:0 auto;padding:28px 24px 96px;}
.rp p{margin:0;max-width:var(--measure);}
.rp strong,.rp b{font-weight:700;color:var(--forest-700);}

.rp .hero{position:relative;overflow:hidden;border-radius:20px;padding:44px 48px 46px;
  background:radial-gradient(120% 150% at 88% 30%,#1E5138 0%,rgba(30,81,56,0) 58%),
             linear-gradient(150deg,var(--forest-800) 0%,var(--forest-900) 62%,#0B2216 100%);
  color:var(--paper);display:grid;grid-template-columns:minmax(0,1fr) auto;
  gap:40px;align-items:center;}
.rp .eyebrow{display:inline-block;font-size:11.5px;font-weight:700;letter-spacing:.13em;
  text-transform:uppercase;padding:7px 13px;border-radius:999px;
  background:rgba(47,191,113,.15);border:1px solid rgba(47,191,113,.34);color:var(--signal-lit);}
.rp .hero h1{font-family:var(--display);font-weight:600;font-size:clamp(32px,4.4vw,52px);
  line-height:1.06;letter-spacing:-.015em;margin:20px 0 14px;text-wrap:balance;color:#FBF9F5;}
.rp .hero p{color:rgba(247,244,238,.76);max-width:46ch;font-size:16px;}
.rp .hero-actions{display:flex;gap:12px;margin-top:26px;flex-wrap:wrap;}
.rp .btn{display:inline-flex;align-items:center;gap:9px;font-family:var(--body);font-size:14.5px;
  font-weight:700;padding:12px 20px;border-radius:10px;border:1px solid transparent;
  cursor:pointer;text-decoration:none;}
.rp .btn-primary{background:var(--signal);color:#06271A;}
.rp .btn-ghost{background:rgba(255,255,255,.08);color:#EFEDE7;border-color:rgba(255,255,255,.18);}
.rp .btn-dark{background:var(--forest-700);color:#F4F1EA;}
.rp .btn:focus-visible{outline:3px solid var(--signal-lit);outline-offset:3px;}

.rp .ring-wrap{display:flex;flex-direction:column;align-items:center;gap:10px;}
.rp .ring{position:relative;width:186px;height:186px;}
.rp .ring svg{transform:rotate(-90deg);display:block;}
.rp .ring-face{position:absolute;inset:0;display:flex;flex-direction:column;
  align-items:center;justify-content:center;}
.rp .ring-band{font-family:var(--display);font-size:25px;font-weight:600;line-height:1.15;
  color:#FBF9F5;text-align:center;max-width:124px;text-wrap:balance;}
.rp .ring-sub{margin-top:6px;font-size:10.5px;letter-spacing:.15em;text-transform:uppercase;
  font-weight:700;color:rgba(247,244,238,.55);}
.rp .ring-note{font-size:12.5px;color:rgba(247,244,238,.6);text-align:center;max-width:190px;}

.rp section.block{margin-top:60px;}
.rp .block-head{display:flex;align-items:baseline;gap:16px;padding-bottom:14px;
  border-bottom:1px solid var(--paper-line);margin-bottom:26px;}
.rp .block-num{font-size:12.5px;font-weight:700;color:var(--signal);letter-spacing:.06em;
  font-variant-numeric:tabular-nums;}
.rp .block-head h2{font-family:var(--display);font-size:clamp(24px,2.7vw,31px);font-weight:600;
  letter-spacing:-.012em;margin:0;color:var(--forest-900);}
.rp .block-body{display:flex;flex-direction:column;gap:22px;}

.rp .care{margin-top:26px;border-radius:16px;padding:30px 34px;
  background:linear-gradient(135deg,#EDF6F0 0%,#E6F1EA 100%);border:1px solid #CFE3D6;
  display:flex;flex-direction:column;gap:12px;}
.rp .care h3{font-family:var(--display);font-size:23px;font-weight:600;margin:0;
  color:var(--forest-800);}
.rp .care p{color:#38493E;}

.rp .bars{display:flex;flex-direction:column;gap:15px;}
.rp .bar-row{display:grid;grid-template-columns:190px minmax(0,1fr) 54px;align-items:center;gap:18px;}
.rp .bar-name{font-size:14.5px;font-weight:500;color:var(--ink);}
.rp .bar-weight{display:block;font-size:11.5px;color:var(--ink-faint);font-weight:400;}
.rp .bar-track{position:relative;height:9px;border-radius:999px;background:#E7E1D6;overflow:hidden;}
.rp .bar-fill{height:100%;border-radius:999px;}
.rp .bar-val{text-align:right;font-size:15px;font-weight:700;font-variant-numeric:tabular-nums;}
.rp .t-critical .bar-fill{background:linear-gradient(90deg,#A8412C,var(--rust));}
.rp .t-critical .bar-val{color:var(--rust);}
.rp .t-watch .bar-fill{background:linear-gradient(90deg,#B87A22,var(--amber));}
.rp .t-watch .bar-val{color:var(--amber);}
.rp .t-ok .bar-fill{background:linear-gradient(90deg,var(--forest-500),var(--signal));}
.rp .t-ok .bar-val{color:var(--forest-500);}

.rp .split{display:grid;grid-template-columns:1fr 1fr;gap:20px;}
.rp .panel{border-radius:15px;padding:24px 26px;background:var(--paper-card);
  border:1px solid var(--paper-line);display:flex;flex-direction:column;gap:16px;}
.rp .panel-title{display:flex;align-items:center;gap:9px;font-size:11.5px;font-weight:700;
  letter-spacing:.12em;text-transform:uppercase;}
.rp .panel-title .dot{width:8px;height:8px;border-radius:50%;}
.rp .panel-strength .panel-title{color:var(--forest-500);}
.rp .panel-strength .dot{background:var(--signal);}
.rp .panel-gap .panel-title{color:var(--rust);}
.rp .panel-gap .dot{background:var(--rust);}
.rp .panel-note{font-size:13.5px;color:var(--ink-soft);}
.rp .chip-list{display:flex;flex-direction:column;gap:11px;}
.rp .chip-row{display:grid;grid-template-columns:minmax(0,1fr) 76px 38px;align-items:center;
  gap:12px;font-size:14px;}
.rp .mini-track{height:6px;border-radius:999px;background:#E7E1D6;overflow:hidden;}
.rp .mini-fill{height:100%;border-radius:999px;}
.rp .chip-num{text-align:right;font-weight:700;font-size:13.5px;font-variant-numeric:tabular-nums;}
.rp .chip-row.t-ok .mini-fill{background:linear-gradient(90deg,var(--forest-500),var(--signal));}
.rp .chip-row.t-ok .chip-num{color:var(--forest-500);}
.rp .chip-row.t-watch .mini-fill{background:linear-gradient(90deg,#B87A22,var(--amber));}
.rp .chip-row.t-watch .chip-num{color:var(--amber);}
.rp .chip-row.t-critical .mini-fill{background:linear-gradient(90deg,#A8412C,var(--rust));}
.rp .chip-row.t-critical .chip-num{color:var(--rust);}

.rp .finding{border-radius:18px;padding:36px 40px 32px;
  background:linear-gradient(150deg,var(--forest-700) 0%,var(--forest-900) 100%);
  color:var(--paper);display:flex;flex-direction:column;gap:22px;}
.rp .finding-tag{display:flex;align-items:center;gap:9px;font-size:11.5px;font-weight:700;
  letter-spacing:.13em;text-transform:uppercase;color:var(--signal-lit);}
.rp .finding-tag .dot{width:8px;height:8px;border-radius:50%;background:var(--signal-lit);}
.rp .finding h3{font-family:var(--display);font-size:clamp(24px,3vw,34px);font-weight:600;
  line-height:1.22;margin:0;max-width:26ch;text-wrap:balance;color:#FBF9F5;}
.rp .finding h3 em{font-style:italic;color:var(--signal-lit);}
.rp .conf-row{display:flex;align-items:center;gap:18px;}
.rp .conf-track{flex:1;height:7px;border-radius:999px;background:rgba(255,255,255,.14);
  overflow:hidden;}
.rp .conf-fill{height:100%;border-radius:999px;
  background:linear-gradient(90deg,var(--signal),#A3E635);}
.rp .conf-num{font-size:20px;font-weight:700;color:var(--signal-lit);
  font-variant-numeric:tabular-nums;}

.rp .cause-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;}
.rp .cause{border-radius:13px;padding:20px 22px;background:var(--paper-card);
  border:1px solid var(--paper-line);display:flex;flex-direction:column;gap:9px;}
.rp .cause-cat{font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
  color:var(--ink-faint);}
.rp .cause-name{font-family:var(--display);font-size:19px;font-weight:600;
  color:var(--forest-800);line-height:1.2;}
.rp .cause-conf{font-size:12.5px;color:var(--ink-soft);font-variant-numeric:tabular-nums;}

.rp .trail{border-radius:15px;padding:28px 30px;background:var(--paper-card);
  border:1px solid var(--paper-line);display:flex;flex-direction:column;gap:16px;}
.rp .trail-head{font-size:11.5px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;
  color:var(--forest-500);}
.rp .trail-step{display:grid;grid-template-columns:26px minmax(0,1fr);gap:14px;align-items:start;}
.rp .step-num{width:24px;height:24px;border-radius:7px;background:#DFF0E4;color:var(--forest-700);
  font-size:12.5px;font-weight:700;display:flex;align-items:center;justify-content:center;
  font-variant-numeric:tabular-nums;}
.rp .trail-step p{font-size:15px;max-width:none;}

.rp .quote{border-left:3px solid var(--signal);padding:4px 0 4px 20px;
  display:flex;flex-direction:column;gap:8px;}
.rp .quote-q{font-size:12.5px;color:var(--ink-faint);font-weight:500;}
.rp .quote-a{font-family:var(--display);font-style:italic;font-size:18px;line-height:1.45;
  color:var(--forest-800);max-width:54ch;}
.rp .quote-read{font-size:14px;color:var(--ink-soft);max-width:58ch;}

.rp .action{display:grid;grid-template-columns:34px minmax(0,1fr);gap:18px;align-items:start;
  padding:22px 26px;border-radius:14px;background:var(--paper-card);
  border:1px solid var(--paper-line);}
.rp .action-num{width:30px;height:30px;border-radius:9px;background:#DFF0E4;
  color:var(--forest-700);font-weight:700;font-size:14px;display:flex;align-items:center;
  justify-content:center;font-variant-numeric:tabular-nums;}
.rp .action-body{display:flex;flex-direction:column;gap:11px;}
.rp .action-text{font-size:15.5px;line-height:1.55;max-width:68ch;}
.rp .action-meta{display:flex;align-items:center;gap:10px;flex-wrap:wrap;}
.rp .tag{font-size:10.5px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
  padding:5px 10px;border-radius:6px;}
.rp .tag-high{background:#DFF0E4;color:#1B5E38;}
.rp .tag-med{background:#F6EBD4;color:#8A5F14;}
.rp .tag-link{background:transparent;color:var(--ink-faint);border:1px solid var(--paper-line);
  letter-spacing:.06em;text-transform:none;font-weight:500;font-size:12px;}

/* auto-fit, not a fixed 3: the roadmap is two cards (a fortnight) and the
   stat strip varies with what the diagnosis produced. A hardcoded count
   leaves a dead column whenever the content does not match it. */
.rp .road{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:18px;}
.rp .road-card{border-radius:14px;padding:24px 24px 26px;background:var(--paper-card);
  border:1px solid var(--paper-line);display:flex;flex-direction:column;gap:14px;}
.rp .road-when{font-size:11px;font-weight:700;letter-spacing:.13em;text-transform:uppercase;
  color:var(--signal);}
.rp .road-card h3{font-family:var(--display);font-size:22px;font-weight:600;margin:0;
  color:var(--forest-900);line-height:1.15;}
.rp .road-list{margin:0;padding:0;list-style:none;display:flex;flex-direction:column;gap:10px;}
.rp .road-list li{display:grid;grid-template-columns:14px minmax(0,1fr);gap:10px;
  font-size:14.5px;line-height:1.5;color:var(--ink-soft);}
.rp .road-list li::before{content:"";width:7px;height:7px;border-radius:50%;
  background:var(--signal);margin-top:8px;}

.rp .stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:18px;}
.rp .stat{border-radius:14px;padding:22px 24px;background:var(--paper-card);
  border:1px solid var(--paper-line);display:flex;flex-direction:column;gap:5px;}
.rp .stat-num{font-family:var(--display);font-size:34px;font-weight:700;color:var(--forest-700);
  line-height:1;font-variant-numeric:tabular-nums;}
.rp .stat-label{font-size:13.5px;color:var(--ink-soft);}

/* Facts: the label/value rows under a narrative section. Open-ended by design
   -- an engine-owned fact key this module has never heard of still renders,
   which is what lets a newly answered Founder-DNA dimension appear on the
   report without a code change. */
.rp .facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));
  gap:16px;margin-top:22px;}
.rp .fact{border-radius:12px;padding:18px 20px;background:var(--paper-card);
  border:1px solid var(--paper-line);display:flex;flex-direction:column;gap:7px;}
.rp .fact-k{font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;
  color:var(--signal);}
.rp .fact-v{font-size:14.5px;line-height:1.55;color:var(--ink-soft);}
.rp .fact-list{margin:0;padding:0;list-style:none;display:flex;flex-direction:column;gap:7px;}
.rp .fact-list li{display:grid;grid-template-columns:14px minmax(0,1fr);gap:9px;}
.rp .fact-list li::before{content:"";width:6px;height:6px;border-radius:50%;
  background:var(--signal);margin-top:8px;}

/* The confirm/solve heading inside Priority actions -- the 3+3 plan reads as
   two moves, not one undifferentiated list of six. */
.rp .action-group{font-size:12px;font-weight:700;letter-spacing:.1em;
  text-transform:uppercase;color:var(--signal);margin:22px 0 14px;}
.rp .action-group:first-child{margin-top:0;}

/* The DISTRESS hero: no ring, so it is one column rather than two. */
.rp .hero-quiet{grid-template-columns:1fr;}

.rp .close{margin-top:60px;border-radius:16px;padding:32px 36px;background:var(--paper-card);
  border:1px solid var(--paper-line);display:flex;align-items:center;
  justify-content:space-between;gap:26px;flex-wrap:wrap;}
.rp .close h3{font-family:var(--display);font-size:25px;font-weight:600;margin:0 0 7px;
  color:var(--forest-900);}
.rp .close p{font-size:15px;color:var(--ink-soft);}
.rp .footnote{margin-top:30px;font-size:13px;color:var(--ink-faint);max-width:var(--measure);}

@media (max-width:860px){
  .rp .hero{grid-template-columns:1fr;padding:34px 26px 36px;}
  .rp .split,.rp .cause-grid,.rp .road,.rp .stats{grid-template-columns:1fr;}
  .rp .bar-row{grid-template-columns:140px minmax(0,1fr) 46px;gap:12px;}
  .rp .shell{padding:18px 16px 70px;}
}
@media (prefers-reduced-motion:reduce){.rp *{animation:none!important;transition:none!important;}}
"""

# The COMPLETE list of what paper changes. Kept short on purpose: everything not
# named here is identical between the screen and the PDF, which is the whole
# point of this module existing.
#
#   1. Buttons go. A "Download PDF" button printed inside the PDF is dead ink --
#      it cannot be clicked, and it tells the reader the document still thinks
#      it is a web page.
#   2. Cards may not straddle a page boundary: a root-cause card split across
#      two sheets reads as two half-findings.
#   3. A fixed shell width, so Chromium lays the page out at the width the
#      design was approved at rather than at the paper's width. Without this the
#      three-column grids reflow and the PDF stops matching the screen.
PRINT_ONLY = """
@page{size:A4;margin:14mm 12mm;}
.rp .hero-actions,.rp .close .btn{display:none!important;}
.rp .shell{max-width:1080px;padding:0 0 8mm;}
.rp .hero{border-radius:16px;break-after:avoid;}
.rp section.block{margin-top:34px;}
.rp .block-head{break-after:avoid;}
.rp .panel,.rp .cause,.rp .action,.rp .road-card,.rp .stat,.rp .trail,
.rp .finding,.rp .care,.rp .quote,.rp .close,.rp .fact{break-inside:avoid;}
.rp .close{margin-top:34px;}
"""
