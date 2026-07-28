"""Ally AI Chat -- Link Intelligence (Phase 6, Milestone 4).

Pure, offline link handling: extract URLs from text, normalize, de-duplicate, detect
the provider (GitHub / YouTube / Google Docs / Drive / Notion / LinkedIn / Twitter /
Website), and build metadata. No crawling, no HTTP requests, no content fetching.
"""

from app.ai_chat.links.errors import InvalidLinkError, LinkError
from app.ai_chat.links.extractor import LinkExtractor
from app.ai_chat.links.metadata import build_metadata, detect_type
from app.ai_chat.links.schemas import Link, LinkMetadata, LinkType
from app.ai_chat.links.validators import is_valid_url, normalize_url

__all__ = [
    "Link",
    "LinkMetadata",
    "LinkType",
    "LinkExtractor",
    "build_metadata",
    "detect_type",
    "is_valid_url",
    "normalize_url",
    "LinkError",
    "InvalidLinkError",
]
