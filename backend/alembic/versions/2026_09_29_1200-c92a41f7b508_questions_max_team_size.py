"""Let a question say it is only for founders BELOW a team size.

`min_team_size` (d4a1f8c62b73) answers "are there enough people here for this
question to have a subject?". It cannot express the opposite, and the first-hire
bank (b48e5c12d709) needs the opposite:

    Is there a job you are doing that you would be glad to hand over?
    What would you need to see before you felt safe paying someone a salary?

Those are the right questions for somebody who has never hired. Put them to a
founder with twelve staff and they read as a diagnosis of a company that does
not exist -- the same defect `min_team_size` was written to fix, pointed the
other way. Twenty questions carried `min_team_size = 'solo'`, which admits
everyone, so every founder at Stage 0->1 was a candidate for them.

WHY A SECOND COLUMN AND NOT A RANGE TYPE. A range would make the common case --
one open-ended bound, which is 1,051 of the 1,071 rows that have any bound at
all -- carry the machinery of the rare one. Two nullable columns read as two
plain questions with the same fail-open answer: unknown admits.

WHY ONLY TWENTY ROWS. This bound is claimed, never inferred. Keyword screening
for team-dependence was tried twice on `min_team_size` and was wrong in both
directions both times, and nothing about reversing the comparison makes the
guessing safer. A question earns a `max_team_size` when somebody has read it and
judged that a larger team makes it meaningless -- so the column starts at the
one bank written for that case and grows by review.

Revision ID: c92a41f7b508
Revises: b48e5c12d709
Create Date: 2026-09-29 12:00:00.000000
"""
from __future__ import annotations

from alembic import op

revision = "c92a41f7b508"
down_revision = "b48e5c12d709"
branch_labels = None
depends_on = None

#: `founders.team_size`'s bands, plus the two d71a4e8c3f05 retired. The retired
#: pair is accepted for the same reason `min_team_size`'s CHECK still accepts
#: them: a mid-deploy write from the old frontend must not fail. Nothing writes
#: them now.
_BANDS = ("solo", "2_5", "6_10", "11_25", "26_plus", "26_50", "50_plus")

_FIRST_HIRE_PREFIX = "FHIRE-"


def upgrade() -> None:
    op.execute("ALTER TABLE questions ADD COLUMN max_team_size VARCHAR(20)")
    values = ", ".join(f"'{b}'" for b in _BANDS)
    op.execute(
        f"""
        ALTER TABLE questions ADD CONSTRAINT questions_max_team_size_check
        CHECK (max_team_size IS NULL OR max_team_size IN ({values}))
        """
    )
    op.execute(
        """
        CREATE INDEX idx_questions_max_team_size ON questions (max_team_size)
        WHERE max_team_size IS NOT NULL
        """
    )
    op.execute(
        f"""
        UPDATE questions SET max_team_size = 'solo'
        WHERE question_code LIKE '{_FIRST_HIRE_PREFIX}%'
        """
    )


def downgrade() -> None:
    # Dropping the column takes the constraint and the index with it, and takes
    # the twenty bounds too -- which is the whole of this migration's data, so
    # there is nothing here to preserve separately the way e4c9b21d8a76 had to.
    op.execute("ALTER TABLE questions DROP COLUMN max_team_size")
