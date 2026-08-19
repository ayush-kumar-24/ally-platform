"""Gotenberg client: HTML -> PDF via the headless-Chromium sidecar.

We POST the self-contained print HTML to Gotenberg's Chromium route and let it
render with the document's own @page CSS (preferCssPageSize) and backgrounds
(printBackground) so the PDF matches the screen. Fonts are already base64-embedded
in the HTML, so Gotenberg needs no network of its own.
"""

from __future__ import annotations

import httpx


class GotenbergError(RuntimeError):
    """Gotenberg was unreachable or returned a non-2xx response."""


def render_pdf(html: str, *, base_url: str, timeout: float = 30.0) -> bytes:
    """Render HTML to PDF bytes. Raises GotenbergError on any failure."""
    url = base_url.rstrip("/") + "/forms/chromium/convert/html"
    files = {"files": ("index.html", html.encode("utf-8"), "text/html")}
    data = {"preferCssPageSize": "true", "printBackground": "true"}
    try:
        resp = httpx.post(url, files=files, data=data, timeout=timeout)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise GotenbergError(f"Gotenberg render failed: {exc}") from exc
    return resp.content


def is_available(*, base_url: str, timeout: float = 3.0) -> bool:
    """Is the Gotenberg sidecar reachable right now?

    Separate from `render_pdf` on purpose: this answers "will report exports be
    screen-accurate" without rendering anything, so it is cheap enough for a
    boot check and a health probe.

    Short timeout, and never raises. Both callers want a fact to report, not an
    exception to handle -- a health endpoint that 500s because the PDF renderer
    is down is worse than one that says the PDF renderer is down.
    """
    try:
        resp = httpx.get(base_url.rstrip("/") + "/health", timeout=timeout)
        return resp.status_code == 200
    except httpx.HTTPError:
        return False
