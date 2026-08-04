"""store the founder's generated first impression

The "Reading between the lines" screen used to interpolate a founder's answers
into four fixed sentences. It now shows a real read produced from what they
actually told us, generated once and kept, so revisiting the screen does not
quietly rewrite the impression Ally claims to have formed.

Adds:
  founders.first_impression      jsonb   the generated read (bullets/read/instinct)
  founders.first_impression_at   timestamptz  when it was produced
  model_task_routing row for the 'first_impression' task

Revision ID: b9d1e3f5a7c2
Revises: e8f0a2c4d6b9
Create Date: 2026-08-04 15:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b9d1e3f5a7c2'
down_revision: Union[str, Sequence[str], None] = 'e8f0a2c4d6b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TASK = "first_impression"


def upgrade() -> None:
    op.add_column(
        "founders",
        sa.Column("first_impression", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "founders",
        sa.Column("first_impression_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Route the new task the same way every other task is seeded. Without an
    # active row, resolve_task_model raises rather than silently defaulting.
    routing = sa.table(
        "model_task_routing",
        sa.column("task", sa.String),
        sa.column("provider", sa.String),
        sa.column("model_id", sa.String),
        sa.column("notes", sa.Text),
    )
    op.bulk_insert(
        routing,
        [{
            "task": _TASK,
            "provider": "anthropic",
            "model_id": "claude-sonnet-5",
            "notes": "founder first impression shown after onboarding",
        }],
    )


def downgrade() -> None:
    op.execute(sa.text("delete from model_task_routing where task = :t").bindparams(t=_TASK))
    op.drop_column("founders", "first_impression_at")
    op.drop_column("founders", "first_impression")
