"""Widen answers.score_label so NOT_APPLICABLE can actually be stored.

BUG, NOT A SEMANTIC CHANGE. Migration c7d18a3f420b widened
`answers_score_label_check` to admit `'not_applicable'` (14 characters) but never
widened the COLUMN, which is `varchar(10)`. The result: every write path that
sets `answer.score_label = ScoreLabel.NOT_APPLICABLE.value` --
`DiagnosisService._apply_insight` chief among them, which is how the adaptive
advisor's read reaches the database -- raises

    ERROR: value too long for type character varying(10)

Reproduced directly against this database before writing this migration:

    INSERT INTO answers (...) VALUES (..., 'not_applicable')
    ERROR:  value too long for type character varying(10)

So Step 4 (feat: three-valued applicability, and N/A that cannot move the score)
made the advisor ABLE to emit `not_applicable`, and every reasoning engine has
correctly handled `ScoreLabel.NOT_APPLICABLE` since before that -- but the one
column that has to hold the value could not, and the state was unreachable in
practice despite being reachable in every test that stubs the column out.

This migration does not touch what the values MEAN. `green`/`amber`/`red`/
`not_applicable` are unchanged; only the column's capacity changes, to 20 --
enough for `not_applicable` (14) plus headroom, matching the convention
`confirmation_status` already uses at `varchar(15)` for its own longest value.

Purely widening, so purely safe: no existing value can fail to fit a larger
column, and the downgrade only re-narrows after confirming nothing has actually
used the space c7d18a3f420b's own downgrade didn't already guard for the
constraint.
"""

from alembic import op
import sqlalchemy as sa

revision = "d1a4c8e2f907"
down_revision = "c5e7b1a94f60"
branch_labels = None
depends_on = None

_NEW_LENGTH = 20
_OLD_LENGTH = 10


def upgrade() -> None:
    op.alter_column(
        "answers", "score_label",
        type_=sa.String(length=_NEW_LENGTH),
        existing_type=sa.String(length=_OLD_LENGTH),
        existing_nullable=True,
    )


def downgrade() -> None:
    # Refuse rather than silently truncate: a stored value longer than 10 chars
    # (in practice, only 'not_applicable') would be corrupted by a narrowing
    # ALTER COLUMN, which is exactly the failure c7d18a3f420b's own downgrade
    # already refuses at the constraint level. This refuses one step earlier, at
    # the column, so the two migrations agree on what "cannot downgrade" means.
    op.execute(
        "DO $$ BEGIN "
        "IF EXISTS (SELECT 1 FROM answers WHERE length(score_label) > 10) THEN "
        "RAISE EXCEPTION 'answers.score_label contains values over 10 characters "
        "(e.g. not_applicable); narrowing would corrupt them. Reclassify first.'; "
        "END IF; END $$;"
    )
    op.alter_column(
        "answers", "score_label",
        type_=sa.String(length=_OLD_LENGTH),
        existing_type=sa.String(length=_NEW_LENGTH),
        existing_nullable=True,
    )
