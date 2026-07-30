"""Deterministic metadata helpers: mime detection, typing, checksum, size.

Pure functions -- no I/O, no parsing of file contents. Mime is detected from the
filename extension (an offline, deterministic mapping); checksum is SHA-256 of the
raw bytes; size is the byte length.
"""

from __future__ import annotations

import hashlib
import os

from app.ai_chat.attachments.schemas import AttachmentType, SupportedMimeType

_EXT_TO_MIME: dict[str, SupportedMimeType] = {
    "pdf": SupportedMimeType.PDF,
    "docx": SupportedMimeType.DOCX,
    "txt": SupportedMimeType.TXT,
    "md": SupportedMimeType.MARKDOWN,
    "markdown": SupportedMimeType.MARKDOWN,
    "png": SupportedMimeType.PNG,
    "jpg": SupportedMimeType.JPEG,
    "jpeg": SupportedMimeType.JPEG,
    "gif": SupportedMimeType.GIF,
    "webp": SupportedMimeType.WEBP,
    "csv": SupportedMimeType.CSV,
}

_MIME_TO_TYPE: dict[SupportedMimeType, AttachmentType] = {
    SupportedMimeType.PDF: AttachmentType.DOCUMENT,
    SupportedMimeType.DOCX: AttachmentType.DOCUMENT,
    SupportedMimeType.TXT: AttachmentType.TEXT,
    SupportedMimeType.MARKDOWN: AttachmentType.TEXT,
    SupportedMimeType.CSV: AttachmentType.SPREADSHEET,
    SupportedMimeType.PNG: AttachmentType.IMAGE,
    SupportedMimeType.JPEG: AttachmentType.IMAGE,
    SupportedMimeType.GIF: AttachmentType.IMAGE,
    SupportedMimeType.WEBP: AttachmentType.IMAGE,
}


def extension_of(filename: str) -> str:
    """Lower-case extension without the dot ('' if none)."""
    return os.path.splitext(filename or "")[1].lstrip(".").lower()


def detect_mime(filename: str) -> SupportedMimeType | None:
    return _EXT_TO_MIME.get(extension_of(filename))


def categorize(mime: SupportedMimeType) -> AttachmentType:
    return _MIME_TO_TYPE[mime]


def checksum(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def size_of(content: bytes) -> int:
    return len(content)


def supported_extensions() -> tuple[str, ...]:
    return tuple(sorted(_EXT_TO_MIME))
