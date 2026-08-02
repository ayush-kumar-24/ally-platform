"""SQL-backed AttachmentRepository -- persists to `file_uploads`.

Same fix, same shape as SqlConversationRepository (app/ai_chat/repositories/
sql_conversation.py): the process-level InMemoryAttachmentRepository singleton
loses every attachment's metadata on restart/redeploy and cannot be shared across
worker processes. This repository is request-scoped (built per-request with the
request's DB session) and durable.

Identity mapping: the domain mints STRING ids (uuid hex); the DB uses an integer
PK internally. file_uploads.external_id (added by migration d4f6a8c0e2b3) holds
the domain attachment_id; the integer upload_id stays the internal PK.

`extension` and `attachment_type` are NOT stored -- both are pure deterministic
functions of file_name / file_type (mime) respectively (attachments/metadata.py),
recomputed on read so they can never drift out of sync with their source.

`storage_path` / `storage_url` are left untouched (no data to write -- see the
migration docstring: no storage backend exists in this codebase yet). This
repository fixes metadata durability only.

FAILS LOUD, not resilient-degrade -- same reasoning as the conversation
repository: this repository IS the attachment metadata storage, so a silent
degrade would mean "your upload succeeded" while its record was actually lost.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai_chat.attachments.metadata import categorize, extension_of
from app.ai_chat.attachments.repository import AttachmentRepository
from app.ai_chat.attachments.schemas import (
    Attachment,
    AttachmentMetadata,
    AttachmentStatus,
    SupportedMimeType,
)
from app.models.schema import Conversations as ConversationRow
from app.models.schema import FileUploads as FileUploadRow

# AttachmentType has 4 values; the legacy upload_category CHECK only allows
# ('file','image') -- kept as a coarse convenience column, NOT the source of
# truth (file_type/mime is, via categorize()).
_IMAGE_CATEGORY = "image"
_FILE_CATEGORY = "file"


class SqlAttachmentRepository(AttachmentRepository):
    def __init__(self, db: Session):
        self.db = db

    def add(self, attachment: Attachment) -> None:
        conv_pk = self._conversation_pk(attachment.conversation_id)
        if conv_pk is None:
            raise LookupError(f"conversation {attachment.conversation_id!r} not found")
        row = FileUploadRow(
            founder_id=attachment.founder_id,
            conversation_id=conv_pk,
            file_name=attachment.metadata.filename,
            file_type=attachment.metadata.mime_type.value,
            file_size_bytes=attachment.metadata.size_bytes,
            upload_category=(
                _IMAGE_CATEGORY if attachment.metadata.mime_type in _IMAGE_MIMES else _FILE_CATEGORY
            ),
            is_active=attachment.is_active,
            message_id=(int(attachment.message_id) if attachment.message_id else None),
            external_id=attachment.attachment_id,
            status=attachment.status.value,
            checksum=attachment.metadata.checksum,
            updated_at=attachment.updated_at,
            archived_at=attachment.archived_at,
            deleted_at=attachment.deleted_at,
            tags=list(attachment.tags),
            extra=dict(attachment.extra),
            created_at=attachment.created_at,
        )
        self.db.add(row)
        self.db.flush()

    def get(self, attachment_id: str) -> Attachment | None:
        result = self.db.execute(
            select(FileUploadRow, ConversationRow.external_id)
            .join(ConversationRow, ConversationRow.conversation_id == FileUploadRow.conversation_id)
            .where(FileUploadRow.external_id == attachment_id)
        ).first()
        if result is None:
            return None
        row, conv_external_id = result
        return self._to_domain(row, conv_external_id)

    def replace(self, attachment: Attachment) -> None:
        row = self._get_row(attachment.attachment_id)
        if row is None:
            raise LookupError(f"attachment {attachment.attachment_id!r} not found")
        row.status = attachment.status.value
        row.is_active = attachment.is_active
        row.updated_at = attachment.updated_at
        row.archived_at = attachment.archived_at
        row.deleted_at = attachment.deleted_at
        row.tags = list(attachment.tags)
        row.extra = dict(attachment.extra)
        self.db.flush()

    def list_for_conversation(
        self, conversation_id: str, *, statuses: tuple[AttachmentStatus, ...]
    ) -> tuple[Attachment, ...]:
        conv_pk = self._conversation_pk(conversation_id)
        if conv_pk is None:
            return ()
        status_values = [s.value for s in statuses]
        stmt = (
            select(FileUploadRow)
            .where(FileUploadRow.conversation_id == conv_pk, FileUploadRow.status.in_(status_values))
        )
        rows = self.db.execute(stmt).scalars().all()
        found = [self._to_domain(r, conversation_id) for r in rows]
        found.sort(key=lambda a: (a.created_at, a.attachment_id))
        return tuple(found)

    def purge(self, attachment_id: str) -> bool:
        row = self._get_row(attachment_id)
        if row is None:
            return False
        self.db.delete(row)
        self.db.flush()
        return True

    # --- mapping helpers -----------------------------------------------

    def _get_row(self, attachment_id: str) -> FileUploadRow | None:
        return self.db.execute(
            select(FileUploadRow).where(FileUploadRow.external_id == attachment_id)
        ).scalar_one_or_none()

    def _conversation_pk(self, conversation_id: str) -> int | None:
        return self.db.execute(
            select(ConversationRow.conversation_id).where(ConversationRow.external_id == conversation_id)
        ).scalar_one_or_none()

    @staticmethod
    def _to_domain(row: FileUploadRow, conversation_id: str | None = None) -> Attachment:
        mime = SupportedMimeType(row.file_type)
        return Attachment(
            attachment_id=row.external_id,
            conversation_id=conversation_id or str(row.conversation_id),
            founder_id=row.founder_id,
            status=AttachmentStatus(row.status),
            metadata=AttachmentMetadata(
                filename=row.file_name,
                extension=extension_of(row.file_name),
                mime_type=mime,
                attachment_type=categorize(mime),
                size_bytes=row.file_size_bytes,
                checksum=row.checksum,
            ),
            created_at=row.created_at,
            updated_at=row.updated_at,
            message_id=(str(row.message_id) if row.message_id is not None else None),
            archived_at=row.archived_at,
            deleted_at=row.deleted_at,
            tags=tuple(row.tags or ()),
            extra=dict(row.extra or {}),
        )


_IMAGE_MIMES = frozenset({
    SupportedMimeType.PNG, SupportedMimeType.JPEG, SupportedMimeType.GIF, SupportedMimeType.WEBP,
})
