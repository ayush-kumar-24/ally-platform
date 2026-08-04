"""Attachment content bytes -- file_uploads gains an actual storage column.

Closes the last piece of the attachment durability gap: `AttachmentService.
add_attachment` validated and hashed uploaded bytes but never stored them (see
d4f6a8c0e2b3's docstring -- "no storage backend exists"). Chat cannot read
what it never kept. This adds `content BYTEA NULL` so the raw bytes persist
alongside the metadata already fixed by d4f6a8c0e2b3.

Nullable, no backfill: the 0 pre-existing rows (and any row uploaded before
this migration) have no bytes to recover. Bounded by the existing 25 MiB
per-file validator cap, so this stays a reasonable Postgres bytea column
rather than needing object storage.

Revision ID: a7c9e1f3b5d7
Revises: f6b8c0d2e4a5
Create Date: 2026-08-02 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'a7c9e1f3b5d7'
down_revision = 'f6b8c0d2e4a5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('file_uploads', sa.Column('content', sa.LargeBinary(), nullable=True))


def downgrade() -> None:
    op.drop_column('file_uploads', 'content')
