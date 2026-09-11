"""questions: an untagged question can no longer be inserted

`questions.primary_stage_group` decides which founders a question may be asked
of. It was nullable, and the diagnosis repository treated NULL as
"stage-agnostic -- eligible for everyone", so a question added without a tag
went to every founder at every stage. Not as an error anybody would see: it
simply appeared in an ideation founder's diagnosis asking about revenue
concentration, and in a scaling founder's asking what is stopping them from
starting.

`questions_primary_stage_group_check` did NOT already prevent this. A SQL CHECK
passes when its expression is NULL rather than FALSE, so
`primary_stage_group = ANY (ARRAY['Stage 0', ...])` constrains the VALUE of a
tag without ever requiring one to be present.

The bank has no untagged rows today (all 1,213 seeded questions are pinned to
exactly one group), so this is a door being closed before anyone walks through
it rather than a repair.

WHY NOT VALID, AND WHY NOT `SET NOT NULL`. `ALTER COLUMN ... SET NOT NULL`
rewrites and revalidates the whole table, and fails outright if a single
legacy row -- on an environment whose bank predates the seeds this repository
carries -- is untagged. That would block the migration on data this migration
cannot see. A `NOT VALID` CHECK enforces on every INSERT and UPDATE from the
moment it is added, which is the entire point here, while leaving rows already
in the table alone. Existing rows are counted and reported below so the gap, if
any, is visible rather than assumed away.

TO FINISH THE JOB on an environment that reports violations: fix the rows, then

    ALTER TABLE questions VALIDATE CONSTRAINT questions_stage_group_required;

which takes no rewrite and only a SHARE UPDATE EXCLUSIVE lock.

Paired with the repository change in the same commit
(app/api/v1/diagnosis/repository.py -- list_candidate_questions), which stops
serving untagged questions even where this constraint has not been validated.

Revision ID: b7e4f2a91c58
Revises: a2d5f74c8e13
Create Date: 2026-09-11 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7e4f2a91c58"
down_revision: Union[str, Sequence[str], None] = "a2d5f74c8e13"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CONSTRAINT = "questions_stage_group_required"


def upgrade() -> None:
    bind = op.get_bind()

    # Reported, not enforced: see the module docstring. A count here is the
    # only place the gap becomes visible -- the constraint below deliberately
    # does not look at existing rows.
    untagged = bind.execute(
        sa.text("SELECT count(*) FROM questions WHERE primary_stage_group IS NULL")
    ).scalar_one()
    if untagged:
        print(
            f"  [{revision}] {untagged} question(s) carry no primary_stage_group. "
            "They are no longer served to any founder (see list_candidate_questions). "
            "Tag them, then: ALTER TABLE questions VALIDATE CONSTRAINT "
            f"{_CONSTRAINT};"
        )

    op.execute(
        f"""
        ALTER TABLE questions
        ADD CONSTRAINT {_CONSTRAINT}
        CHECK (primary_stage_group IS NOT NULL)
        NOT VALID
        """
    )


def downgrade() -> None:
    op.execute(f"ALTER TABLE questions DROP CONSTRAINT IF EXISTS {_CONSTRAINT}")
