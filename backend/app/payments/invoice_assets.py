"""Brand assets for the invoice, embedded rather than linked.

Gotenberg renders with NO NETWORK OF ITS OWN (see reports/gotenberg.py), and
that single fact decides everything in this module. A linked logo renders as a
broken-image box; a linked webfont silently falls back and the PDF ships in the
wrong typeface with nothing to signal it. Both failures are invisible until a
founder is looking at the document. So every byte the page needs travels inside
the page, and the failure mode becomes impossible instead of merely unlikely.

Everything here is cached for the process's life: the logo and the three faces
are identical on every receipt, and base64-encoding ~170KB on each download to
produce the same string is pure waste.
"""

from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

from app.core.config import settings
from app.core.logger import logger

_ASSET_DIR = Path(__file__).parent / "assets"

#: The report PDF's font directory. Shared rather than copied: these are the
#: same two faces the Clarity Report is set in, and a receipt in a different
#: typeface would not look like it came from the same company. Reaching across
#: for them follows what invoice_pdf.py already does with reports.gotenberg --
#: the PDF stack is shared infrastructure in this codebase, not the report's
#: private property.
_FONT_DIR = Path(__file__).resolve().parents[1] / "api" / "v1" / "reports" / "assets" / "fonts"

#: The Ally mark, transparent background, as the sidebar and the marketing site
#: use it. NOT `ally-logo.png`, which is the same mark baked onto a cream
#: rounded square -- that tile would sit on the white document as a visible
#: grey-ish box.
DEFAULT_LOGO = _ASSET_DIR / "ally-logo-mark.png"

#: The GoXL Entrepreneurship wordmark, for the FOOTER, beside the legal entity
#: that issues the document. Two marks, two jobs: the header says what the
#: founder bought (GoXL Ally), the footer says who billed them for it.
#:
#: Lifted from the company's own existing invoice PDF, which is the only place
#: it exists in a usable form. `frontend/public/goxl-logo.svg` was recovered
#: from git history first and is NOT this: it is a 498-byte placeholder that
#: sets the letters "GoXL" in Inter with a white-to-green gradient, so on white
#: paper its left half fades out entirely. It was deliberately not used.
#:
#: Opaque white background rather than transparency -- it is composited onto
#: the white footer, where white is invisible, and keying it out by hand would
#: risk a halo around the letterforms for no gain.
COMPANY_LOGO = _ASSET_DIR / "goxl-entrepreneurship-logo.png"


@lru_cache(maxsize=4)
def _data_uri(path: str, mime: str) -> str | None:
    """A file as a data: URI, or None if it cannot be read.

    None rather than an exception: a missing logo must degrade to a document
    with no logo, never to a founder who cannot get their receipt. The header
    is built to hold together without it.
    """
    try:
        data = base64.b64encode(Path(path).read_bytes()).decode()
    except OSError as exc:
        logger.warning("invoice brand asset could not be read; rendering without it",
                       extra={"path": path}, exc_info=exc)
        return None
    return f"data:{mime};base64,{data}"


def logo_data_uri() -> str | None:
    """The brand mark for the document header.

    `INVOICE_LOGO_PATH` overrides the bundled Ally mark, so a combined
    GoXL/Ally lockup (or any updated artwork) can be dropped in without a code
    change. Anything Chromium renders works; PNG and SVG are the sensible ones.
    """
    configured = (settings.INVOICE_LOGO_PATH or "").strip()
    if configured:
        mime = "image/svg+xml" if configured.lower().endswith(".svg") else "image/png"
        return _data_uri(configured, mime)
    return _data_uri(str(DEFAULT_LOGO), "image/png")


def company_logo_data_uri() -> str | None:
    """The issuing company's mark for the footer.

    Optional in exactly the way the header mark is: unreadable means a footer
    without it, never a founder who cannot get their receipt.
    """
    configured = (settings.INVOICE_COMPANY_LOGO_PATH or "").strip()
    if configured:
        mime = "image/svg+xml" if configured.lower().endswith(".svg") else "image/png"
        return _data_uri(configured, mime)
    return _data_uri(str(COMPANY_LOGO), "image/png")


@lru_cache(maxsize=1)
def font_face_css() -> str:
    """Just the faces this document sets type in.

    The report embeds four (Inter and Fraunces, roman and italic) because its
    prose uses all of them. This document has no italic BODY text, so Inter's
    italic is left out -- every face is ~45KB before base64 inflates it by a
    third, and a receipt is a document founders email to their accountants.
    Fraunces italic stays because the lockup's `Ally` is set in it.

    A face that will not load is skipped rather than fatal: the CSS names web-
    safe fallbacks after each family, so the document degrades to system type
    instead of to an error.
    """
    faces = []
    for family, style, filename in (
        ("Inter", "normal", "inter-normal.woff2"),
        ("Fraunces", "normal", "fraunces-normal.woff2"),
        # The real italic, not a synthesised oblique. It is carried for one
        # word -- the `Ally` in the lockup -- and that is the word the document
        # is branded with; a browser-slanted serif next to the actual mark is
        # the kind of small wrongness that makes a PDF look generated rather
        # than issued. Inter's italic is NOT carried: no body text uses it.
        ("Fraunces", "italic", "fraunces-italic.woff2"),
    ):
        try:
            data = base64.b64encode((_FONT_DIR / filename).read_bytes()).decode()
        except OSError as exc:
            logger.warning("invoice font could not be embedded; falling back to system type",
                           extra={"font": filename}, exc_info=exc)
            continue
        faces.append(
            f"@font-face{{font-family:'{family}';font-style:{style};font-weight:100 900;"
            f"font-display:swap;src:url(data:font/woff2;base64,{data}) format('woff2');}}"
        )
    return "".join(faces)
