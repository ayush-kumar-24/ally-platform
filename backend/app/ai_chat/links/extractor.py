"""LinkExtractor (Phase 6, Milestone 4, Part 4).

Pure parsing: find http(s) URLs in text, normalize, de-duplicate, detect provider,
and build metadata. No crawling, no HTTP requests, no content fetching. Deterministic
-- identical text yields identical, order-preserving links.
"""

from __future__ import annotations

import re

from app.ai_chat.links.errors import InvalidLinkError
from app.ai_chat.links.metadata import build_metadata, detect_type
from app.ai_chat.links.schemas import Link, LinkType
from app.ai_chat.links.validators import is_valid_url, normalize_url

_URL_FINDER = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_TRAILING = ".,;:!?)]}>\"'"


def _strip_trailing(url: str) -> str:
    return url.rstrip(_TRAILING)


class LinkExtractor:
    def extract(self, text: str) -> tuple[Link, ...]:
        seen: set[str] = set()
        links: list[Link] = []
        for match in _URL_FINDER.finditer(text or ""):
            raw = _strip_trailing(match.group(0))
            if not is_valid_url(raw):
                continue
            metadata = build_metadata(raw)
            if metadata.url in seen:                      # de-duplicate by normalized url
                continue
            seen.add(metadata.url)
            links.append(Link(url=metadata.url, link_type=metadata.link_type, metadata=metadata))
        return tuple(links)

    def parse(self, url: str) -> Link:
        """Parse a single URL, failing closed on a malformed one."""
        raw = _strip_trailing((url or "").strip())
        if not is_valid_url(raw):
            raise InvalidLinkError(url)
        metadata = build_metadata(raw)
        return Link(url=metadata.url, link_type=metadata.link_type, metadata=metadata)

    def detect_type(self, url: str) -> LinkType:
        if not is_valid_url((url or "").strip()):
            return LinkType.UNKNOWN
        return build_metadata(url).link_type

    def from_messages(self, messages) -> tuple[Link, ...]:
        """Compose around ConversationService (Part 5): extract unique links across
        message contents. Read-only -- it consumes `.content`, mutating nothing."""
        seen: set[str] = set()
        out: list[Link] = []
        for message in messages:
            for link in self.extract(getattr(message, "content", "") or ""):
                if link.url not in seen:
                    seen.add(link.url)
                    out.append(link)
        return tuple(out)
