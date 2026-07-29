"""Fail-closed attachment validation. No content parsing -- only shape checks."""

from __future__ import annotations

from app.ai_chat.attachments.errors import (
    AttachmentTooLargeError,
    InvalidAttachmentError,
    UnsupportedAttachmentError,
)
from app.ai_chat.attachments.metadata import detect_mime, extension_of, supported_extensions

DEFAULT_MAX_SIZE_BYTES = 25 * 1024 * 1024  # 25 MiB


def validate_content(content: bytes) -> None:
    if not isinstance(content, (bytes, bytearray)):
        raise InvalidAttachmentError("content must be bytes")
    if len(content) == 0:
        raise InvalidAttachmentError("content is empty")


def validate_filename(filename: str) -> None:
    if not filename or not filename.strip():
        raise InvalidAttachmentError("filename is empty")
    if not extension_of(filename):
        raise UnsupportedAttachmentError(f"'{filename}' has no extension")
    if detect_mime(filename) is None:
        raise UnsupportedAttachmentError(
            f"'.{extension_of(filename)}' (supported: {', '.join(supported_extensions())})"
        )


def validate_size(size: int, max_size: int) -> None:
    if size <= 0:
        raise InvalidAttachmentError("size must be positive")
    if size > max_size:
        raise AttachmentTooLargeError(size, max_size)
