"""file_uploads: durable-persistence columns for the attachment resume fix

Same shape as the conversations fix (c3e5f7a9b1d2). Adds what the domain
Attachment needs that the table didn't carry:
  - external_id: the string id AttachmentService already mints (uuid hex) -- the
    domain identifies attachments by this, not the internal integer upload_id.
  - status/archived_at/deleted_at: the domain's 3-state lifecycle (active/
    archived/deleted); the table only had a 2-state is_active boolean.
  - checksum: sha256 of the upload, used for duplicate detection. Cannot be
    derived after the fact (the raw bytes are never stored -- see below).
  - updated_at, tags, extra: round-tripped by the service on every lifecycle
    transition; without columns they'd be silently dropped.

extension and attachment_type are NOT stored: both are pure deterministic
functions of file_name / file_type (mime) respectively (see attachments/
metadata.py), so the repository recomputes them on read instead of duplicating
data that could drift out of sync with its source.

storage_path is relaxed to nullable. It was NOT NULL, but no layer in this
codebase currently stores the uploaded bytes anywhere -- AttachmentService reads
them only to derive size/checksum/mime, then discards them (see
attachments/service.py, chat/router.py upload_attachment). This repository fixes
the metadata-durability bug; it does not add a storage backend, so there is
nothing correct to put in that column today.

Revision ID: d4f6a8c0e2b3
Revises: c3e5f7a9b1d2
Create Date: 2026-08-02 09:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "d4f6a8c0e2b3"
down_revision: Union[str, Sequence[str], None] = "c3e5f7a9b1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("file_uploads", sa.Column("external_id", sa.String(length=64), nullable=True))
    op.add_column(
        "file_uploads",
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'active'")),
    )
    op.add_column("file_uploads", sa.Column("checksum", sa.String(length=64), nullable=True))
    op.add_column(
        "file_uploads",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.add_column("file_uploads", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("file_uploads", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "file_uploads",
        sa.Column("tags", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    op.add_column(
        "file_uploads",
        sa.Column("extra", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )

    # Backfill any pre-existing rows (none in production today) before enforcing
    # NOT NULL + UNIQUE on external_id / checksum.
    op.execute("UPDATE file_uploads SET external_id = 'legacy-' || upload_id::text WHERE external_id IS NULL")
    op.execute("UPDATE file_uploads SET checksum = 'unknown-' || upload_id::text WHERE checksum IS NULL")
    op.alter_column("file_uploads", "external_id", nullable=False)
    op.alter_column("file_uploads", "checksum", nullable=False)
    op.create_unique_constraint("file_uploads_external_id_key", "file_uploads", ["external_id"])
    op.create_index("ix_file_uploads_external_id", "file_uploads", ["external_id"])
    op.create_index("ix_file_uploads_conversation_id", "file_uploads", ["conversation_id"])

    op.create_check_constraint(
        "file_uploads_status_check", "file_uploads",
        "status IN ('active','archived','deleted')",
    )

    # No storage backend exists yet (see module docstring) -- nothing correct to
    # write here today, so the column can no longer block inserts.
    op.alter_column("file_uploads", "storage_path", nullable=True)


def downgrade() -> None:
    op.alter_column("file_uploads", "storage_path", nullable=False,
                    server_default=sa.text("''"))
    op.execute("UPDATE file_uploads SET storage_path = '' WHERE storage_path IS NULL")
    op.alter_column("file_uploads", "storage_path", server_default=None)
    op.drop_constraint("file_uploads_status_check", "file_uploads", type_="check")
    op.drop_index("ix_file_uploads_conversation_id", table_name="file_uploads")
    op.drop_index("ix_file_uploads_external_id", table_name="file_uploads")
    op.drop_constraint("file_uploads_external_id_key", "file_uploads", type_="unique")
    op.drop_column("file_uploads", "extra")
    op.drop_column("file_uploads", "tags")
    op.drop_column("file_uploads", "deleted_at")
    op.drop_column("file_uploads", "archived_at")
    op.drop_column("file_uploads", "updated_at")
    op.drop_column("file_uploads", "checksum")
    op.drop_column("file_uploads", "status")
    op.drop_column("file_uploads", "external_id")
