"""Ally AI Chat -- File Attachments (Phase 6, Milestone 4).

Structured, metadata-only attachment handling: validation, mime detection, checksum,
size, lifecycle (archive/restore/delete), per-conversation listing + summary. No
OCR, no embeddings, no content parsing.
"""

from app.ai_chat.attachments.errors import (
    AttachmentError,
    AttachmentNotFoundError,
    AttachmentTooLargeError,
    DuplicateAttachmentError,
    InvalidAttachmentError,
    UnsupportedAttachmentError,
)
from app.ai_chat.attachments.metadata import (
    categorize,
    checksum,
    detect_mime,
    extension_of,
    size_of,
    supported_extensions,
)
from app.ai_chat.attachments.repository import (
    AttachmentRepository,
    InMemoryAttachmentRepository,
)
from app.ai_chat.attachments.schemas import (
    Attachment,
    AttachmentMetadata,
    AttachmentStatus,
    AttachmentSummary,
    AttachmentType,
    SupportedMimeType,
)
from app.ai_chat.attachments.service import (
    AttachmentConfig,
    AttachmentService,
    build_attachment_service,
)

__all__ = [
    # schemas
    "Attachment",
    "AttachmentMetadata",
    "AttachmentSummary",
    "AttachmentType",
    "AttachmentStatus",
    "SupportedMimeType",
    # repository
    "AttachmentRepository",
    "InMemoryAttachmentRepository",
    # service
    "AttachmentService",
    "AttachmentConfig",
    "build_attachment_service",
    # metadata helpers
    "detect_mime",
    "categorize",
    "checksum",
    "size_of",
    "extension_of",
    "supported_extensions",
    # errors
    "AttachmentError",
    "UnsupportedAttachmentError",
    "AttachmentTooLargeError",
    "InvalidAttachmentError",
    "AttachmentNotFoundError",
    "DuplicateAttachmentError",
]
