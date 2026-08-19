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

Blob location is per-row, not global: `storage_path` set means the bytes are
an S3 object under that key; NULL means they are inline in `content`
(migration a7c9e1f3b5d7), bounded by the 25 MiB upload cap. Which one a new
upload uses depends purely on whether a bucket is configured, so pointing at
S3 later needs no backfill -- older rows keep resolving from Postgres. See
attachments/storage.py.

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
from app.ai_chat.attachments.storage import ObjectStorage, ObjectStorageError, object_key
from app.core.logger import logger
from app.models.schema import Conversations as ConversationRow
from app.models.schema import FileUploads as FileUploadRow

# AttachmentType has 4 values; the legacy upload_category CHECK only allows
# ('file','image') -- kept as a coarse convenience column, NOT the source of
# truth (file_type/mime is, via categorize()).
# file_uploads.message_id is an INTEGER column (the messages table's own PK),
# but ai_chat's domain message ids are the uuid `messages.id` -- a 32-char hex
# string that cannot go in an integer column. Rather than migrate the column's
# type, the chat linkage is packed into the existing `extra` JSONB under an
# internal underscore key and stripped back out on read. That is the same
# convention sql_conversation.py already documents and uses for the fields the
# messages table has no column for.
_MESSAGE_ID_KEY = "_message_id"

_IMAGE_CATEGORY = "image"
_FILE_CATEGORY = "file"


class SqlAttachmentRepository(AttachmentRepository):
    def __init__(self, db: Session, storage: ObjectStorage | None = None):
        self.db = db
        # None = keep bytes inline (the default, and what local dev/CI run on).
        self.storage = storage

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
            # Left NULL: see _MESSAGE_ID_KEY above. A domain (uuid) id would
            # raise ValueError here, and did not previously because nothing set
            # message_id at upload time.
            message_id=None,
            external_id=attachment.attachment_id,
            status=attachment.status.value,
            checksum=attachment.metadata.checksum,
            updated_at=attachment.updated_at,
            archived_at=attachment.archived_at,
            deleted_at=attachment.deleted_at,
            tags=list(attachment.tags),
            extra=({**attachment.extra, _MESSAGE_ID_KEY: attachment.message_id}
                   if attachment.message_id else dict(attachment.extra)),
            created_at=attachment.created_at,
        )
        self.db.add(row)
        # Deliberately flush, not commit: add_attachment() always calls
        # add_content() straight after, and the two are one upload. Committing
        # here would let a failure in add_content leave a metadata row whose
        # bytes never arrived -- an attachment the chat can list but never read.
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
        extra = dict(attachment.extra)
        if attachment.message_id:
            extra[_MESSAGE_ID_KEY] = attachment.message_id
        else:
            extra.pop(_MESSAGE_ID_KEY, None)
        row.extra = extra
        self.db.commit()

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
        # Remove the object first: if this fails the row stays, which is
        # recoverable -- deleting the row first would orphan the object with
        # nothing left pointing at it.
        if row.storage_path and self.storage is not None:
            try:
                self.storage.delete(row.storage_path)
            except ObjectStorageError as exc:
                logger.error("attachments: S3 delete failed; row kept",
                             extra={"stage": "s3_delete", "attachment_id": attachment_id,
                                    "error": str(exc)})
                raise
        self.db.delete(row)
        self.db.commit()
        return True

    def add_content(self, attachment_id: str, content: bytes) -> None:
        row = self._get_row(attachment_id)
        if row is None:
            raise LookupError(f"attachment {attachment_id!r} not found")
        stored_to_s3 = False
        if self.storage is not None:
            key = object_key(row.founder_id, attachment_id, extension_of(row.file_name))
            try:
                self.storage.put(key, content, content_type=row.file_type)
                row.storage_path = key
                row.content = None      # single source of truth per row
                stored_to_s3 = True
            except ObjectStorageError as exc:
                # A storable attachment beats a failed upload: record it
                # inline and say so, rather than 500-ing on a bucket problem.
                logger.error("attachments: S3 put failed; storing inline instead",
                             extra={"stage": "s3_put", "attachment_id": attachment_id,
                                    "error": str(exc)})
        if not stored_to_s3:
            row.content = content

        # Commits the whole upload (metadata from add() + these bytes).
        # get_db() only closes the session, and SessionLocal is
        # autocommit=False, so a flush-only write is rolled back when the
        # request ends: uploads returned 201 and then silently vanished, which
        # also left the chat with nothing to feed the LLM.
        self.db.commit()

    def get_content(self, attachment_id: str) -> bytes | None:
        row = self.db.execute(
            select(FileUploadRow.content, FileUploadRow.storage_path)
            .where(FileUploadRow.external_id == attachment_id)
        ).one_or_none()
        if row is None:
            return None
        content, storage_path = row
        # The row decides, not the current config: a file uploaded before the
        # bucket existed still reads back correctly after S3 is switched on.
        if storage_path:
            if self.storage is None:
                logger.warning("attachments: row points at object storage but none "
                               "is configured; cannot read",
                               extra={"stage": "s3_get", "attachment_id": attachment_id})
                return None
            return self.storage.get(storage_path)
        return content

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
            message_id=(
                (row.extra or {}).get(_MESSAGE_ID_KEY)
                or (str(row.message_id) if row.message_id is not None else None)
            ),
            archived_at=row.archived_at,
            deleted_at=row.deleted_at,
            tags=tuple(row.tags or ()),
            # internal key stripped so callers never see it
            extra={k: v for k, v in (row.extra or {}).items() if k != _MESSAGE_ID_KEY},
        )


_IMAGE_MIMES = frozenset({
    SupportedMimeType.PNG, SupportedMimeType.JPEG, SupportedMimeType.GIF, SupportedMimeType.WEBP,
})
