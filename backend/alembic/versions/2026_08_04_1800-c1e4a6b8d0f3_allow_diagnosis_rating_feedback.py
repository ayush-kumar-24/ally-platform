"""allow 'diagnosis_rating' feedback

founder_feedback already permits report_rating and general, which cover two of
the three moments we ask at. The third -- immediately after a diagnosis
completes -- happens before a report exists, so it has a session_id and no
report_id. Filing it as 'general' would make it indistinguishable from
unprompted dashboard feedback, which is exactly the distinction the learning
engine needs.

Revision ID: c1e4a6b8d0f3
Revises: b9d1e3f5a7c2
Create Date: 2026-08-04 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = 'c1e4a6b8d0f3'
down_revision: Union[str, Sequence[str], None] = 'b9d1e3f5a7c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CONSTRAINT = "founder_feedback_feedback_type_check"
_BASE = (
    "'report_rating', 'recommendation_helpful', 'outcome_30day', "
    "'outcome_60day', 'outcome_90day', 'general'"
)


def upgrade() -> None:
    op.execute(f"ALTER TABLE founder_feedback DROP CONSTRAINT {_CONSTRAINT}")
    op.execute(
        f"ALTER TABLE founder_feedback ADD CONSTRAINT {_CONSTRAINT} "
        f"CHECK (feedback_type::text = ANY (ARRAY[{_BASE}, 'diagnosis_rating']::text[]))"
    )


def downgrade() -> None:
    """Rows of the new type would violate the old constraint, so they go first.
    Lossy, and deliberately so -- the alternative is a migration that fails."""
    op.execute("DELETE FROM founder_feedback WHERE feedback_type = 'diagnosis_rating'")
    op.execute(f"ALTER TABLE founder_feedback DROP CONSTRAINT {_CONSTRAINT}")
    op.execute(
        f"ALTER TABLE founder_feedback ADD CONSTRAINT {_CONSTRAINT} "
        f"CHECK (feedback_type::text = ANY (ARRAY[{_BASE}]::text[]))"
    )
