"""Per-stage diagnosis question budget.

How many questions a diagnosis is allowed to ask is currently one integer in
code -- `settings.MAX_DIAGNOSIS_QUESTIONS`, 30 for every founder at every stage.
Two things read it, and both are wrong to read a global:

  * `service._attach_question` uses it as the completion CEILING.
  * `confidence.build_confidence_inputs` uses it as the coverage DENOMINATOR,
    a signal carrying 25% of the confidence score.

The denominator is the one that bites. A Stage 0 founder for whom twelve
questions is genuinely enough scores 12/30 = 0.40 on a quarter of the total,
which drags their achievable score below the report threshold. Confidence never
crosses, so they never finish early -- they run to 30 regardless of how well
they answered, and half of those 30 land on pillars (Revenue, Product, Team)
that a founder with an idea and nothing built cannot speak to at all.

This is the same failure the denominator has already had once. It used to be
the founder's whole in-scope bank -- 569 questions for Stage 0->1 -- so thirty
answers scored 0.05 and capped the total at 76 against a threshold of 80. That
was fixed by changing 569 to 30. This migration makes the next move: from a
constant to the stage's own number.

DELIBERATELY SEEDED AS NULL
---------------------------
Every row stays NULL here, and NULL means "fall back to
MAX_DIAGNOSIS_QUESTIONS". So applying this migration changes NOTHING about how
any diagnosis behaves -- it is inert until somebody sets a number.

That is on purpose. What each stage's budget should be is a product decision
that has not been taken yet, and encoding a guess in a migration would make it
look decided. Once it is decided it is an UPDATE, not a deploy:

    UPDATE founder_stages SET question_budget = 12 WHERE stage_order = 1;
    UPDATE founder_stages SET question_budget = 25 WHERE stage_order BETWEEN 2 AND 4;
    UPDATE founder_stages SET question_budget = 32 WHERE stage_order >= 5;

(Those are illustrative, not a recommendation.) Same principle the project
already applies to scoring_rules and model_task_routing: the rule is data.

The CHECK exists because a zero here would be a division by zero in the
coverage signal. The reading code guards it too -- a constraint and a guard,
because this value is edited by hand in production and a hand-edit is exactly
the path a validation-free column gets a 0 down.

Revision ID: c6a4e83f19d7
Revises: a7f3c1d92b04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c6a4e83f19d7"
down_revision = "a7f3c1d92b04"
branch_labels = None
depends_on = None

_TABLE = "founder_stages"
_COLUMN = "question_budget"
_CHECK = "founder_stages_question_budget_positive"


def upgrade() -> None:
    # Guarded rather than bare: this project has had columns applied by hand to
    # production RDS ahead of the migration that defines them (see
    # scripts/embedding_migration/RUNBOOK_founder_dna_rds.md), so a replay must
    # not abort the whole upgrade on a column that is already there.
    bind = op.get_bind()
    existing = {c["name"] for c in sa.inspect(bind).get_columns(_TABLE)}

    if _COLUMN not in existing:
        op.add_column(_TABLE, sa.Column(_COLUMN, sa.Integer(), nullable=True))

    op.execute(
        f"ALTER TABLE public.{_TABLE} DROP CONSTRAINT IF EXISTS {_CHECK}"
    )
    op.create_check_constraint(_CHECK, _TABLE, f"{_COLUMN} IS NULL OR {_COLUMN} > 0")


def downgrade() -> None:
    op.execute(f"ALTER TABLE public.{_TABLE} DROP CONSTRAINT IF EXISTS {_CHECK}")

    bind = op.get_bind()
    existing = {c["name"] for c in sa.inspect(bind).get_columns(_TABLE)}
    if _COLUMN in existing:
        op.drop_column(_TABLE, _COLUMN)
