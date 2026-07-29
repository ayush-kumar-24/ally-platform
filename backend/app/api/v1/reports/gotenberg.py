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
