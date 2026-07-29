"""Deterministic provider detection + LinkMetadata construction. Pure parsing."""

from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

from app.ai_chat.links.schemas import LinkMetadata, LinkType
from app.ai_chat.links.validators import normalize_url


def _host_is(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def detect_type(host: str, path: str = "") -> LinkType:
    host = (host or "").lower()
    if not host:
        return LinkType.UNKNOWN
    if host == "docs.google.com":
        return LinkType.GOOGLE_DOCS
    if host == "drive.google.com":
        return LinkType.GOOGLE_DRIVE
    if _host_is(host, "github.com"):
        return LinkType.GITHUB
    if _host_is(host, "youtube.com") or _host_is(host, "youtu.be"):
        return LinkType.YOUTUBE
    if _host_is(host, "notion.so") or _host_is(host, "notion.site"):
        return LinkType.NOTION
    if _host_is(host, "linkedin.com"):
        return LinkType.LINKEDIN
    if _host_is(host, "twitter.com") or _host_is(host, "x.com"):
        return LinkType.TWITTER
    return LinkType.WEBSITE


def _resource_id(link_type: LinkType, parts) -> str | None:
    host = (parts.hostname or "").lower()
    segments = [s for s in parts.path.split("/") if s]
    if link_type == LinkType.YOUTUBE:
        if _host_is(host, "youtu.be"):
            return segments[0] if segments else None
        vals = parse_qs(parts.query).get("v")
        return vals[0] if vals else None
    if link_type == LinkType.GITHUB and len(segments) >= 2:
        return f"{segments[0]}/{segments[1]}"
    if link_type in (LinkType.GOOGLE_DOCS, LinkType.GOOGLE_DRIVE) and "d" in segments:
        i = segments.index("d")
        return segments[i + 1] if i + 1 < len(segments) else None
    return None


def build_metadata(url: str) -> LinkMetadata:
    normalized = normalize_url(url)
    parts = urlsplit(normalized)
    link_type = detect_type(parts.hostname or "", parts.path)
    return LinkMetadata(
        url=normalized, original=url, scheme=parts.scheme, host=parts.hostname or "",
        path=parts.path, query=parts.query, is_secure=(parts.scheme == "https"),
        link_type=link_type, resource_id=_resource_id(link_type, parts),
    )
