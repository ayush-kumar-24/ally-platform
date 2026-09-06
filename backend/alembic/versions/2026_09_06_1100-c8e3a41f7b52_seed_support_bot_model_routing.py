"""Seed model routing for the two support-bot tasks.

`resolve_task_model` fails loudly when a task has no active row -- deliberately,
because a silent default is how a task ends up running on whatever model was
cheapest to import. So the support bot cannot make a model call at all until
these two rows exist.

WHY TWO TASKS AND NOT ONE. Routing picks which published answers fit a founder's
question; answering writes a reply from only those answers. They have very
different shapes -- routing reads a 4,000-token index and returns a handful of
numbers, answering reads three answers and writes 120 words -- so they are
separated now, while it costs nothing, rather than after somebody wants to move
routing to a cheaper model and finds the two welded together.

Both seed to the same model as every other task, for the same reason the
original seed gave: one model while the behaviour is being validated.

WITHOUT THIS the bot still works. It falls back to keyword search over the same
content and answers most questions correctly -- just less well, because
plainto_tsquery cannot tell that "I can't get in" and "I've forgotten my
password" are the same question. The fallback is the safety net, not the plan.

Revision ID: c8e3a41f7b52
Revises: b4d927f1a6c8
Create Date: 2026-09-06 11:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "c8e3a41f7b52"
down_revision = "b4d927f1a6c8"
branch_labels = None
depends_on = None

TASKS = ("support_routing", "support_answer")


def upgrade() -> None:
    # ON CONFLICT DO NOTHING: the row may already have been added by hand while
    # testing, and re-pointing a task somebody has deliberately moved to another
    # model would be a rude thing for a migration to do.
    op.execute(
        sa.text(
            """
            INSERT INTO model_task_routing (task, provider, model_id, is_active, notes)
            VALUES
              ('support_routing', 'anthropic', 'claude-sonnet-5', TRUE,
               'help bot: match a founder question to published answer ids'),
              ('support_answer',  'anthropic', 'claude-sonnet-5', TRUE,
               'help bot: write a reply from only the routed answers')
            ON CONFLICT (task) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM model_task_routing WHERE task IN :tasks").bindparams(
            sa.bindparam("tasks", value=TASKS, expanding=True)
        )
    )
