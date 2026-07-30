"""Link domain entities (Phase 6, Milestone 4, Part 3).

Value objects produced by parsing text -- never persisted, never fetched. Metadata
only: what the link IS (provider, host, path, resource id), not what it contains.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class LinkType(str, Enum):
    WEBSITE = "website"
    GITHUB = "github"
    YOUTUBE = "youtube"
    GOOGLE_DOCS = "google_docs"
    GOOGLE_DRIVE = "google_drive"
    NOTION = "notion"
    LINKEDIN = "linkedin"
    TWITTER = "twitter"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class LinkMetadata:
    url: str                      # normalized
    original: str                 # exactly as found in the text
    scheme: str
    host: str
    path: str
    query: str
    is_secure: bool
    link_type: LinkType
    resource_id: str | None = None   # e.g. youtube video id, github "owner/repo"


@dataclass(frozen=True)
class Link:
    url: str                      # normalized
    link_type: LinkType
    metadata: LinkMetadata
