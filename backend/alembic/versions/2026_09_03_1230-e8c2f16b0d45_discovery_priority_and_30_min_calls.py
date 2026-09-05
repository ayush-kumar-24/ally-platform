"""Discovery calls: 30-minute default and a priority stamp.

Two changes to `discovery_calls`:

- `duration_minutes` default 45 -> 30. Existing rows are left alone on purpose:
  they record calls that were booked as 45-minute slots, and rewriting them
  would make the history disagree with what actually happened.
- `is_priority`, stamped at booking time when the founder's plan carries
  Feature.PRIORITY_CALL (Rs 999). NOT NULL with a false default so every
  existing row reads as non-priority, which is what they were.
"""

import sqlalchemy as sa
from alembic import op

revision = "e8c2f16b0d45"
down_revision = "d7b1e05a9c34"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "discovery_calls",
        sa.Column("is_priority", sa.Boolean(), nullable=False,
                  server_default=sa.text("false")),
    )
    op.alter_column("discovery_calls", "duration_minutes",
                    server_default=sa.text("30"))


def downgrade() -> None:
    op.alter_column("discovery_calls", "duration_minutes",
                    server_default=sa.text("45"))
    op.drop_column("discovery_calls", "is_priority")
