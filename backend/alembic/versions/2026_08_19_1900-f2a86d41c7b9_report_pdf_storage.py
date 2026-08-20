"""remember a report's rendered PDF, and that someone is waiting for one

Report exports rendered on every download and fell back to a plain reportlab
document whenever Gotenberg was unreachable -- silently, since both paths return
200 with a real application/pdf body. A founder who downloaded during a blip got
the wrong document permanently, because nothing ever tried again.

Two columns replace that:

  pdf_storage_key   where the rendered PDF lives once it exists, so a download
                    is a fetch rather than a render. Null until one is made.
  pdf_requested_at  set when a download could not be served because Gotenberg
                    was down. It is the demand signal the backfill sweep reads,
                    so the only PDFs rendered off the request path are ones a
                    founder actually asked for.

Deliberately NOT pre-rendering every report: most are never downloaded, and
rendering all of them would spend Chromium time on documents nobody opens.

Revision ID: f2a86d41c7b9
Revises: e91c5b3a2df4
Create Date: 2026-08-19 19:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2a86d41c7b9"
down_revision: Union[str, Sequence[str], None] = "e91c5b3a2df4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("founder_reports", sa.Column("pdf_storage_key", sa.Text(), nullable=True))
    op.add_column(
        "founder_reports",
        sa.Column("pdf_requested_at", sa.DateTime(timezone=True), nullable=True),
    )
    # The sweep's only query: reports someone is waiting on. Partial, because
    # the rows that satisfy it are a vanishing fraction of the table.
    op.create_index(
        "ix_founder_reports_pdf_pending",
        "founder_reports",
        ["pdf_requested_at"],
        postgresql_where=sa.text("pdf_requested_at is not null and pdf_storage_key is null"),
    )


def downgrade() -> None:
    op.drop_index("ix_founder_reports_pdf_pending", table_name="founder_reports")
    op.drop_column("founder_reports", "pdf_requested_at")
    op.drop_column("founder_reports", "pdf_storage_key")
