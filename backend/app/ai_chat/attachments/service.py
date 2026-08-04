"""AttachmentService (Phase 6, Milestone 4, Part 2).

Repository-driven, deterministic (injected clock + id_factory). Validates, derives
metadata (mime/type/size/checksum), assigns an id + timestamps, and manages the
attachment lifecycle (archive / restore / delete / list / summarize). Contents are
never parsed or interpreted here -- metadata derivation only; the raw bytes are
stored as-is (via `add_content`) so a later reader (chat grounding) can decide
what to do with them, e.g. decode text files. `get_content` is that read path.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from typing import Callable, Mapping

from app.ai_chat.attachments.errors import AttachmentNotFoundError, DuplicateAttachmentError
from app.ai_chat.attachments.metadata import categorize, checksum, detect_mime, extension_of, size_of
from app.ai_chat.attachments.repository import AttachmentRepository
from app.ai_chat.attachments.schemas import (
    Attachment,
    AttachmentMetadata,
    AttachmentStatus,
    AttachmentSummary,
)
from app.ai_chat.attachments.validators import (
    DEFAULT_MAX_SIZE_BYTES,
    validate_content,
    validate_filename,
    validate_size,
)
from app.ai_chat.clock import Clock, SystemClock

_ACTIVE = AttachmentStatus.ACTIVE
_ARCHIVED = AttachmentStatus.ARCHIVED
_DELETED = AttachmentStatus.DELETED


class AttachmentConfig:
    def __init__(self, *, max_size_bytes: int = DEFAULT_MAX_SIZE_BYTES, allow_duplicates: bool = False):
        self.max_size_bytes = max_size_bytes
        self.allow_duplicates = allow_duplicates


class AttachmentService:
    def __init__(
        self,
        repository: AttachmentRepository,
        *,
        clock: Clock | None = None,
        id_factory: Callable[[], str] | None = None,
        config: AttachmentConfig | None = None,
    ):
        self.repository = repository
        self.clock = clock or SystemClock()
        self._new_id = id_factory or (lambda: uuid.uuid4().hex)
        self.config = config or AttachmentConfig()

    # --- create ----------------------------------------------------------

    def add_attachment(
        self,
        conversation_id: str,
        founder_id: int,
        filename: str,
        content: bytes,
        *,
        message_id: str | None = None,
        tags: tuple[str, ...] = (),
        extra: Mapping | None = None,
    ) -> Attachment:
        validate_content(content)
        validate_filename(filename)
        size = size_of(content)
        validate_size(size, self.config.max_size_bytes)

        mime = detect_mime(filename)             # validated non-None above
        digest = checksum(content)
        if not self.config.allow_duplicates:
            self._reject_duplicate(conversation_id, digest)

        now = self.clock.now()
        attachment = Attachment(
            attachment_id=self._new_id(),
            conversation_id=conversation_id,
            founder_id=founder_id,
            status=_ACTIVE,
            metadata=AttachmentMetadata(
                filename=filename, extension=extension_of(filename), mime_type=mime,
                attachment_type=categorize(mime), size_bytes=size, checksum=digest,
            ),
            created_at=now, updated_at=now, message_id=message_id,
            tags=tuple(tags), extra=dict(extra or {}),
        )
        self.repository.add(attachment)
        self.repository.add_content(attachment.attachment_id, content)
        return attachment

    # --- read ------------------------------------------------------------

    def get_attachment(self, attachment_id: str) -> Attachment:
        return self._require(attachment_id)

    def get_content(self, attachment_id: str) -> bytes | None:
        """The raw uploaded bytes, or None if the attachment doesn't exist / has
        none stored. Callers decide how to interpret them (e.g. decode text)."""
        return self.repository.get_content(attachment_id)

    def list_attachments(
        self, conversation_id: str, *, include_archived: bool = False, include_deleted: bool = False
    ) -> tuple[Attachment, ...]:
        statuses = [_ACTIVE]
        if include_archived:
            statuses.append(_ARCHIVED)
        if include_deleted:
            statuses.append(_DELETED)
        return self.repository.list_for_conversation(conversation_id, statuses=tuple(statuses))

    # --- lifecycle -------------------------------------------------------

    def archive_attachment(self, attachment_id: str) -> Attachment:
        now = self.clock.now()
        return self._transition(attachment_id, _ARCHIVED, archived_at=now)

    def restore_attachment(self, attachment_id: str) -> Attachment:
        return self._transition(attachment_id, _ACTIVE, archived_at=None, deleted_at=None)

    def delete_attachment(self, attachment_id: str) -> Attachment:
        now = self.clock.now()
        return self._transition(attachment_id, _DELETED, deleted_at=now)

    # --- summarize -------------------------------------------------------

    def summarize(self, conversation_id: str) -> AttachmentSummary:
        items = self.repository.list_for_conversation(
            conversation_id, statuses=(_ACTIVE, _ARCHIVED, _DELETED))
        counts_by_type: dict[str, int] = {}
        total_bytes = 0
        active = archived = deleted = 0
        for a in items:
            counts_by_type[a.metadata.attachment_type.value] = \
                counts_by_type.get(a.metadata.attachment_type.value, 0) + 1
            if a.is_active:
                active += 1
                total_bytes += a.metadata.size_bytes
            elif a.is_archived:
                archived += 1
            else:
                deleted += 1
        return AttachmentSummary(
            conversation_id=conversation_id, total=len(items), active=active,
            archived=archived, deleted=deleted, total_bytes=total_bytes,
            counts_by_type=counts_by_type,
        )

    # --- internals -------------------------------------------------------

    def _require(self, attachment_id: str) -> Attachment:
        attachment = self.repository.get(attachment_id)
        if attachment is None:
            raise AttachmentNotFoundError(attachment_id)
        return attachment

    def _transition(self, attachment_id: str, target: AttachmentStatus, **changes) -> Attachment:
        attachment = self._require(attachment_id)
        if attachment.status == target and all(getattr(attachment, k) == v for k, v in changes.items()):
            return attachment                                  # idempotent
        updated = replace(attachment, status=target, updated_at=self.clock.now(), **changes)
        self.repository.replace(updated)
        return updated

    def _reject_duplicate(self, conversation_id: str, digest: str) -> None:
        for existing in self.repository.list_for_conversation(conversation_id, statuses=(_ACTIVE,)):
            if existing.metadata.checksum == digest:
                raise DuplicateAttachmentError(digest)


def build_attachment_service(
    repository: AttachmentRepository | None = None,
    *,
    clock: Clock | None = None,
    id_factory: Callable[[], str] | None = None,
    config: AttachmentConfig | None = None,
) -> AttachmentService:
    from app.ai_chat.attachments.repository import InMemoryAttachmentRepository

    return AttachmentService(repository or InMemoryAttachmentRepository(),
                             clock=clock, id_factory=id_factory, config=config)
