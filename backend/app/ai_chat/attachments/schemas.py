"""Attachment domain entities (Phase 6, Milestone 4, Part 1).

Metadata only -- immutable frozen dataclasses describing an uploaded file. Contents
are NEVER parsed, embedded, or OCR'd here; an Attachment records what the file is
(type, mime, size, checksum) and its lifecycle, nothing about what it contains.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping


class AttachmentType(str, Enum):
    DOCUMENT = "document"          # pdf, docx
    TEXT = "text"                 # txt, markdown
    SPREADSHEET = "spreadsheet"   # csv
    IMAGE = "image"               # png, jpg/jpeg, gif, webp


class AttachmentStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"           # soft-deleted; recoverable via restore


class SupportedMimeType(str, Enum):
    PDF = "application/pdf"
    DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    TXT = "text/plain"
    MARKDOWN = "text/markdown"
    PNG = "image/png"
    JPEG = "image/jpeg"
    GIF = "image/gif"
    WEBP = "image/webp"
    CSV = "text/csv"


@dataclass(frozen=True)
class AttachmentMetadata:
    """Descriptive, content-free attributes of the file."""

    filename: str
    extension: str                # lower-case, no dot (e.g. "pdf")
    mime_type: SupportedMimeType
    attachment_type: AttachmentType
    size_bytes: int
    checksum: str                 # sha256 hex of the bytes


@dataclass(frozen=True)
class Attachment:
    attachment_id: str
    conversation_id: str
    founder_id: int
    status: AttachmentStatus
    metadata: AttachmentMetadata
    created_at: datetime
    updated_at: datetime
    message_id: str | None = None
    archived_at: datetime | None = None
    deleted_at: datetime | None = None
    tags: tuple[str, ...] = ()
    extra: Mapping[str, Any] = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        return self.status == AttachmentStatus.ACTIVE

    @property
    def is_archived(self) -> bool:
        return self.status == AttachmentStatus.ARCHIVED

    @property
    def is_deleted(self) -> bool:
        return self.status == AttachmentStatus.DELETED


@dataclass(frozen=True)
class AttachmentSummary:
    conversation_id: str
    total: int
    active: int
    archived: int
    deleted: int
    total_bytes: int
    counts_by_type: Mapping[str, int]
