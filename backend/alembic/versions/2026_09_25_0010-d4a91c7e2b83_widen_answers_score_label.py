"""Widen answers.score_label so not_applicable can actually be stored

Revision ID: d4a91c7e2b83
Revises: c9f41b8e3a07
Create Date: 2026-09-25 00:10:00.000000

`answers.score_label` was varchar(10). Its own CHECK constraint has permitted
'not_applicable' -- fourteen characters -- since the fourth band was added:

    CHECK (score_label = ANY (ARRAY['green','amber','red','not_applicable']))

So the value the constraint allows never fit in the column. Every write of it
failed with

    psycopg2.errors.StringDataRightTruncation:
    value too long for type character varying(10)

which surfaces to the founder as a 500 and DiagnosisPersistenceError("Could not
save your progress"), killing the diagnosis mid-session.

THE EFFECT WAS SILENT AND WIDER THAN A CRASH. Because nothing could ever write
the band, every piece of machinery built for it was unreachable:

  * ScoreLabel.NOT_APPLICABLE (app/models/enums.py) and its is_scored() guard
  * the classifier's fourth-label branch and NOT_APPLICABLE rubric
    (reasoning/engines/diagnostic.py) -- including the _LABEL_TO_SCORE entry
    that maps it to None rather than zero
  * its exclusion from BOTH the numerator and the denominator of the pillar
    score (diagnostic.py), so an inapplicable question would not drag a pillar
    down
  * symptom_detection.py not counting it as a symptom
  * root_cause.py never turning it into evidence

All of that is correct code that could not run. In practice a founder answering
"N/A -- we have no free tier" was classified Red, the strongest negative signal
available, and then quoted back to them in the report as a symptom. Measured on
a keyed run: both N/A answers scored red at score 2.0, in pillars that came out
Critical Gap.

varchar(20), not text: it keeps a bound on a column whose legal values are
fixed by the CHECK above, and leaves room for a future band name without
another migration. The CHECK is unchanged -- it was already right.
"""

from alembic import op
import sqlalchemy as sa

revision = "d4a91c7e2b83"
down_revision = "c9f41b8e3a07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "answers",
        "score_label",
        existing_type=sa.String(length=10),
        type_=sa.String(length=20),
        existing_nullable=True,
    )


def downgrade() -> None:
    # Anything already stored as 'not_applicable' would not fit back into
    # varchar(10), so clear those rows first rather than failing the migration
    # halfway. They are unscored by definition, so a null loses no score --
    # and the pre-widening schema could not represent them at all.
    op.execute(
        "update answers set score_label = null, score = null "
        "where score_label = 'not_applicable'"
    )
    op.alter_column(
        "answers",
        "score_label",
        existing_type=sa.String(length=20),
        type_=sa.String(length=10),
        existing_nullable=True,
    )
