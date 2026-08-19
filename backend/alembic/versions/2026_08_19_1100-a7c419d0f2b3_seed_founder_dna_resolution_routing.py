"""seed model_task_routing for founder_dna_dimension_resolution

The Founder DNA phase's one adaptive decision -- "has this dimension been said
enough about to stop asking" -- runs through
app/api/v1/founder_dna/deps.py::get_dimension_resolution_advisor, which calls
provider_for_task(LLMTask.FOUNDER_DNA_DIMENSION_RESOLUTION). That task was
added to LLMTask.ALL (app/services/llm/router.py) but never seeded by any
migration: b2c4d6e8f0a1 predates it and seeded seven tasks, b9d1e3f5a7c2 added
only 'first_impression'.

resolve_task_model raises LLMConfigurationError when a task has no active row,
and deps.py catches exactly that and returns None. That fail-open is correct
behaviour, but it is silent: the phase then runs fully deterministic, with
dimensions marked resolved by question COUNT alone and no answer ever read by
a model, while ADAPTIVE_QUESTIONS=true and every log looks healthy.

The Supabase development database does NOT have this problem -- someone
inserted the row by hand on 2026-08-17, and llm_call_log shows the task
running normally there. This migration exists so that is true by construction
on every OTHER environment (a fresh database, CI, and production RDS, where it
is unverified) instead of depending on a manual step nobody recorded.

Idempotent insert, precisely because an environment may already have been
patched by hand.

Revision ID: a7c419d0f2b3
Revises: f1a4e6c8b302
Create Date: 2026-08-19 11:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7c419d0f2b3"
# Chained onto f1a4e6c8b302, NOT c3f7a2e8d914. Both were authored against the
# same parent on separate branches, and merging them left `alembic heads`
# reporting two heads -- which makes `alembic upgrade head` refuse to run at
# all, on a database already stamped at f1a4e6c8b302. This migration only
# inserts a config row, so it has no ordering dependency on the avatar column;
# re-parenting it is the whole fix.
down_revision: Union[str, Sequence[str], None] = "f1a4e6c8b302"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TASK = "founder_dna_dimension_resolution"


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            insert into model_task_routing (task, provider, model_id, notes)
            select :task, 'anthropic', 'claude-sonnet-5',
                   'founder DNA dimension resolution (one yes/no per answer)'
            where not exists (
                select 1 from model_task_routing where task = :task
            )
            """
        ).bindparams(task=_TASK)
    )


def downgrade() -> None:
    op.execute(
        sa.text("delete from model_task_routing where task = :task").bindparams(task=_TASK)
    )
