"""Vision territory images.

A founder can attach one picture to each vision territory -- the thing they are
actually working toward, next to the sentence describing it.

Two columns rather than one, mirroring `founders.avatar_url` /
`avatar_storage_path` exactly:

  * image_url          what the browser loads.
  * image_storage_path which backend actually holds THIS file ("s3:<key>" or
                       "local:<name>"). Without it, switching the deployment to
                       S3 later would orphan every image uploaded before the
                       switch, because nothing would record where the old ones
                       went. Avatars learned this the hard way; vision images
                       start with the answer.

Both nullable and no default: an absent image is genuinely absent, not an empty
string, and every existing territory row keeps working untouched.

Revision ID: a7f3c1d92b04
Revises: 9d2f5a4c81be
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a7f3c1d92b04"
down_revision = "9d2f5a4c81be"
branch_labels = None
depends_on = None

_TABLE = "vision_territories"


def upgrade() -> None:
    # Guarded rather than bare: this table is created by an earlier migration
    # in this same chain, but the columns are added idempotently so a database
    # that has already been patched by hand (which has happened on this project)
    # replays cleanly instead of aborting the whole upgrade.
    bind = op.get_bind()
    existing = {c["name"] for c in sa.inspect(bind).get_columns(_TABLE)}

    if "image_url" not in existing:
        op.add_column(_TABLE, sa.Column("image_url", sa.Text(), nullable=True))
    if "image_storage_path" not in existing:
        op.add_column(_TABLE, sa.Column("image_storage_path", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    existing = {c["name"] for c in sa.inspect(bind).get_columns(_TABLE)}

    if "image_storage_path" in existing:
        op.drop_column(_TABLE, "image_storage_path")
    if "image_url" in existing:
        op.drop_column(_TABLE, "image_url")
