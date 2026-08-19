"""Avatar S3 storage path -- founders gains a storage-location column

Revision ID: f1a4e6c8b302
Revises: c3f7a2e8d914
Create Date: 2026-08-18 18:00:00

Same pattern as file_uploads.storage_path (migration a7c9e1f3b5d7 for chat
attachments): a non-null avatar_storage_path means the photo is an S3 object
under that key, NULL means it is on local disk under /uploads/avatars (the
only place it has ever lived until now). Recorded per row, not globally, so
switching S3 on needs no backfill and no flag day -- avatars uploaded before
this keep resolving from local disk exactly as before.

Reuses the exact same S3 bucket/config (ATTACHMENT_S3_BUCKET) and the same
attachments/ key prefix as chat attachments (see avatar_object_key() in
profile/routes.py) -- no new IAM grant or env var needed to turn this on
once it is already on for attachments.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f1a4e6c8b302"
down_revision: Union[str, Sequence[str], None] = "c3f7a2e8d914"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "founders",
        sa.Column("avatar_storage_path", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("founders", "avatar_storage_path")
