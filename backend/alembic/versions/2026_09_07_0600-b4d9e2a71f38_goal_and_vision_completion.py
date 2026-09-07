"""Goal and vision-territory completion.

WHY A TIMESTAMP AND NOT A BOOLEAN

Both columns answer "has the founder reached this?", and a boolean would
answer only that. The achievement written when one flips carries a date, and
that date is not the day someone happens to read the row -- it is the day the
founder said they got there. A nullable timestamp is the same fact plus the
one detail the feature actually needs, at the same cost.

WHY NULLABLE WITH NO DEFAULT

"Still open" is genuinely the absence of a completion, not a completion at
some sentinel date. Every existing row is open, which is exactly what NULL
already says about them -- so this backfills nothing and rewrites no rows.

Both are additive and nullable, so an older container serving traffic during
a rollout neither sees nor writes them and keeps working unchanged.

Revision ID: b4d9e2a71f38
Revises: f1c8d3a26b47
"""

from alembic import op
import sqlalchemy as sa

revision = "b4d9e2a71f38"
down_revision = "f1c8d3a26b47"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "founder_goals",
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "vision_territories",
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("vision_territories", "completed_at")
    op.drop_column("founder_goals", "completed_at")
