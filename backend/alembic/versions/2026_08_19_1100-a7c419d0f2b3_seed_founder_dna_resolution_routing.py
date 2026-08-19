"""seed model_task_routing for founder_dna_dimension_resolution

The Founder DNA phase's one adaptive decision -- "has this dimension been
said enough about to stop asking" -- runs through
app/api/v1/founder_dna/deps.py::get_dimension_resolution_advisor, which calls
provider_for_task(LLMTask.FOUNDER_DNA_DIMENSION_RESOLUTION). That task was
added to LLMTask.ALL (app/services/llm/router.py) but NEVER seeded into
model_task_routing: b2c4d6e8f0a1 predates it and seeded seven tasks,
b9d1e3f5a7c2 added only 'first_impression'.

resolve_task_model raises LLMConfigurationError when a task has no active
row, and deps.py catches exactly that and returns None -- correct as a
fail-open, but it meant the advisor was never constructed on any environment.
The phase therefore ran fully deterministic: dimensions were marked resolved
only by pool exhaustion (a question COUNT), no answer was ever read by a
model, and the "N of 14 dimensions understood" a founder sees was a counter,
not a judgement. Silently, with ADAPTIVE_QUESTIONS=true set and looking
correct in every log.

Idempotent insert, because production may already have had this row patched
in by hand.

Revision ID: a7c419d0f2b3
Revises: c3f7a2e8d914
Create Date: 2026-08-19 11:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7c419d0f2b3"
down_revision: Union[str, Sequence[str], None] = "c3f7a2e8d914"
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
