"""Fix "how well you X" -> "how well your X" in the question bank

Revision ID: b3c9d15e8a47
Revises: f2a86d41c7b9
Create Date: 2026-08-20 13:00:00

Two seeded questions read "how well you product" and "how well you pricing".
Both are shown verbatim to every founder mid-diagnosis, so the typo is on
screen at the exact moment we are asking them to trust the assessment.

Matched on the exact broken string rather than by id alone, so this is a no-op
on any database where the text has already been corrected by hand -- the same
guarded-update shape as d4b8e2c15f70 (repair_inverted_answer_scores).

Question 105 ("what you personally think the product will need") was checked
and deliberately left alone: that one is correct English, not the same typo.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "b3c9d15e8a47"
down_revision: Union[str, Sequence[str], None] = "f2a86d41c7b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


#: (question_id, broken text, corrected text)
_FIXES: tuple[tuple[int, str, str], ...] = (
    (
        92,
        "Rate from 1 to 5 how well you pricing balances covering costs and enticing customers.",
        "Rate from 1 to 5 how well your pricing balances covering costs and enticing customers.",
    ),
    (
        106,
        "Rate from 1 to 5 how well you product currently solves the target problem",
        "Rate from 1 to 5 how well your product currently solves the target problem.",
    ),
)


def upgrade() -> None:
    for qid, broken, fixed in _FIXES:
        op.execute(
            """
            UPDATE questions
               SET question_text = %s
             WHERE question_id = %s
               AND question_text = %s
            """ % (_q(fixed), qid, _q(broken))
        )


def downgrade() -> None:
    for qid, broken, fixed in _FIXES:
        op.execute(
            """
            UPDATE questions
               SET question_text = %s
             WHERE question_id = %s
               AND question_text = %s
            """ % (_q(broken), qid, _q(fixed))
        )


def _q(value: str) -> str:
    """Single-quote a literal for inline SQL, doubling any embedded quotes."""
    return "'" + value.replace("'", "''") + "'"
