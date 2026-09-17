"""Allow the NOT_APPLICABLE answer label.

The three-band rubric (green/amber/red) had no way to express "this question
does not apply to my business", so such an answer was classified Red -- the
strongest negative signal available. Measured in QA: a logistics founder
answering "this isn't really a product business" drove Product to maximum
category risk and surfaced feature-backlog advice as his first action.

Widens `answers_score_label_check` only. `answers.score` and
`answers.score_label` are already nullable, so a NOT_APPLICABLE answer stores a
NULL score without further change, and `answers_score_check` is untouched
(NULL satisfies a CHECK by definition). No existing row changes: the three old
values remain valid, so this is additive and the downgrade is safe as long as
no NOT_APPLICABLE row has been written.

Revision ID: c7d18a3f420b
Revises: b4f2a91c7e63
"""
from alembic import op

revision = "c7d18a3f420b"
down_revision = "b4f2a91c7e63"
branch_labels = None
depends_on = None

_CONSTRAINT = "answers_score_label_check"
_OLD = "(score_label)::text = ANY (ARRAY['green'::text, 'amber'::text, 'red'::text])"
_NEW = ("(score_label)::text = ANY (ARRAY['green'::text, 'amber'::text, "
        "'red'::text, 'not_applicable'::text])")


def upgrade() -> None:
    op.execute(f'ALTER TABLE answers DROP CONSTRAINT IF EXISTS "{_CONSTRAINT}"')
    op.execute(f'ALTER TABLE answers ADD CONSTRAINT "{_CONSTRAINT}" CHECK ({_NEW})')


def downgrade() -> None:
    # Refuses rather than silently dropping data: a stored NOT_APPLICABLE row
    # cannot satisfy the old constraint, and quietly rewriting it to a scored
    # band would reintroduce exactly the defect this migration exists to fix.
    op.execute(
        "DO $$ BEGIN "
        "IF EXISTS (SELECT 1 FROM answers WHERE score_label = 'not_applicable') THEN "
        "RAISE EXCEPTION 'answers.score_label contains not_applicable rows; "
        "reclassify them before downgrading'; END IF; END $$;"
    )
    op.execute(f'ALTER TABLE answers DROP CONSTRAINT IF EXISTS "{_CONSTRAINT}"')
    op.execute(f'ALTER TABLE answers ADD CONSTRAINT "{_CONSTRAINT}" CHECK ({_OLD})')
