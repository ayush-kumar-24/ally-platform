"""Attachment errors (Phase 6, Milestone 4). Extend the ai_chat error tree so
failures map to precise HTTP statuses and fail closed."""

from fastapi import status

from app.ai_chat.errors import ChatError


class AttachmentError(ChatError):
    """Base for attachment failures."""


class UnsupportedAttachmentError(AttachmentError):
    def __init__(self, detail: str):
        super().__init__(f"Unsupported attachment: {detail}.",
                         status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)


class AttachmentTooLargeError(AttachmentError):
    def __init__(self, size: int, limit: int):
        # 413 as a literal: the named Starlette constant was renamed
        # (REQUEST_ENTITY_TOO_LARGE -> CONTENT_TOO_LARGE); the number is stable.
        super().__init__(f"Attachment is {size} bytes; limit is {limit}.", status_code=413)


class InvalidAttachmentError(AttachmentError):
    def __init__(self, reason: str):
        super().__init__(f"Invalid attachment: {reason}.", status_code=422)


class AttachmentNotFoundError(AttachmentError):
    def __init__(self, attachment_id: str):
        super().__init__(f"Attachment '{attachment_id}' was not found.",
                         status_code=status.HTTP_404_NOT_FOUND)


class DuplicateAttachmentError(AttachmentError):
    def __init__(self, checksum: str):
        super().__init__(f"An identical attachment (checksum {checksum[:12]}…) already exists.",
                         status_code=status.HTTP_409_CONFLICT)
