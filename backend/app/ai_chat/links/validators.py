"""URL validation + deterministic normalization. Pure parsing -- no network."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TRACKING_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "gclid", "fbclid", "mc_cid", "mc_eid",
})


def is_valid_url(url: str) -> bool:
    try:
        parts = urlsplit((url or "").strip())
    except ValueError:
        return False
    return parts.scheme in ("http", "https") and bool(parts.netloc) and bool(parts.hostname)


def normalize_url(url: str) -> str:
    """Deterministic canonical form: lower-case scheme+host, drop default ports and
    fragment, strip a trailing slash, remove tracking params, sort the query. Same
    logical URL -> same string (so de-duplication is exact)."""
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()

    netloc = host
    port = parts.port
    if port is not None and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        netloc = f"{host}:{port}"

    path = parts.path or ""
    if path.endswith("/"):
        path = path.rstrip("/")           # "/x/" -> "/x"; root "/" -> "" (clean canonical form)

    kept = sorted((k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                  if k.lower() not in _TRACKING_PARAMS)
    query = urlencode(kept)

    return urlunsplit((scheme, netloc, path, query, ""))
