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
