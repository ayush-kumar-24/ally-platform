"""recompute answers.score from score_label, repairing the inverted values

app/api/v1/diagnosis/advisor.py wrote answers.score with green=2 … red=0 while
the scoring schema (scoring_rules: QUESTION_SCORE_GREEN=0, _AMBER=1, _RED=2)
and every reader treat it as RISK, higher-is-worse. The code is fixed, but the
fix only governs answers written from now on -- every row already stored is
still inverted, and business_health.py reads the stored number, so every
existing report keeps its backwards pillar bands until the data is repaired.

Measured before writing this: one founder's 30 answers scored 25 red + 5 amber
summed to 5 instead of 55, producing 92/100 and "Strong" on all six pillars for
a pre-revenue founder who had never interviewed a customer.

Why this is a safe recompute rather than a guess
------------------------------------------------
`score_label` is the authoritative band -- advisor.py parses it straight from
the model's JSON and it was never inverted. `score` is a derived number. So
this does not "flip" anything: it recomputes the derived column from the
authoritative one, which lands on the correct value whichever convention the
row was written under. Running it twice changes nothing.

Rows with score_label IS NULL are left alone. There is nothing authoritative to
recompute them from, and StoredScoreAnswerClassifier already derives a label
from `score` using the config bands when the label is missing.

Reports are NOT regenerated here. A stored report is a document that was shown
to a founder on a date; silently rewriting its contents is worse than leaving
it and re-running the diagnosis. Use POST /admin/users/{id}/regenerate-report
for the founders whose reports should be reissued.

Revision ID: d4b8e2c15f70
Revises: c8a1f47b93de
Create Date: 2026-08-19 16:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4b8e2c15f70"
down_revision: Union[str, Sequence[str], None] = "c8a1f47b93de"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            update answers
               set score = case score_label
                             when 'green' then 0
                             when 'amber' then 1
                             when 'red'   then 2
                           end
             where score_label is not null
               and score is distinct from (case score_label
                                             when 'green' then 0
                                             when 'amber' then 1
                                             when 'red'   then 2
                                           end)
            """
        )
    )


def downgrade() -> None:
    """Deliberately a no-op.

    The previous values were wrong, and they are not recoverable from anything
    else in the row -- restoring them would mean re-deriving the inversion,
    which is the bug. Rolling this migration back would only put backwards
    numbers back into reports.
    """
