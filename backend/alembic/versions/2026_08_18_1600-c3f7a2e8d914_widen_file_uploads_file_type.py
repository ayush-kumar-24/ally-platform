"""Widen file_uploads.file_type -- varchar(50) could not hold the DOCX mime

Revision ID: c3f7a2e8d914
Revises: bb6617156c6c
Create Date: 2026-08-18 16:00:00

file_type stores the full MIME string. The Office OpenXML types are far
longer than the 50 chars the column was created with:

    application/vnd.openxmlformats-officedocument.wordprocessingml.document

is 71 characters, so EVERY .docx upload failed at INSERT with
StringDataRightTruncation and the endpoint answered 500 -- verified live.
DOCX has been an accepted type (SupportedMimeType) and has had working text
extraction (attachments/extraction.py) the whole time; only the column was
too narrow, so the feature could never actually be used for Word documents.

150 rather than 71: the spreadsheet sibling
(...spreadsheetml.sheet, 65) and any future OpenXML type land in the same
range, and this stays comfortably under the point where a varchar length
would matter for storage in Postgres.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3f7a2e8d914"
down_revision: Union[str, Sequence[str], None] = "bb6617156c6c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "file_uploads", "file_type",
        existing_type=sa.String(length=50),
        type_=sa.String(length=150),
        existing_nullable=False,
    )


def downgrade() -> None:
    # Widening is not reversible without data loss: any row written since the
    # upgrade may hold a value longer than 50 chars (that is the entire point
    # of the change), and narrowing would truncate it. Rows are removed first
    # so the type change cannot silently corrupt a stored MIME type.
    op.execute("DELETE FROM file_uploads WHERE length(file_type) > 50")
    op.alter_column(
        "file_uploads", "file_type",
        existing_type=sa.String(length=150),
        type_=sa.String(length=50),
        existing_nullable=False,
    )
