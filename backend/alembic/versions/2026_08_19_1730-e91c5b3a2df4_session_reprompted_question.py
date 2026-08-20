"""remember which question a founder has already been re-asked once

The diagnosis answer gate (3fc60dd) discards an answer that does not address the
question and re-asks it. With no memory of having done so, it can do it again on
the next attempt, and the next -- the question never advances and the founder
cannot get past it. Reproduced on a full journey run: the same question was
rejected three times and the diagnosis stalled at 15 of 30 with no report.

The judgement is a model's, so it can be wrong, and a wrong one must never trap
someone. This column bounds it: a question may be re-asked at most ONCE. The
founder gets a single nudge, and whatever they send next is accepted and scored
normally.

Nullable int rather than a counter, because "which question is currently in its
second attempt" is the entire question being asked -- a count would also need
clearing whenever the question changed, and that is the bug waiting to happen.

Revision ID: e91c5b3a2df4
Revises: d4b8e2c15f70
Create Date: 2026-08-19 17:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e91c5b3a2df4"
down_revision: Union[str, Sequence[str], None] = "d4b8e2c15f70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("reprompted_question_id", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sessions", "reprompted_question_id")
