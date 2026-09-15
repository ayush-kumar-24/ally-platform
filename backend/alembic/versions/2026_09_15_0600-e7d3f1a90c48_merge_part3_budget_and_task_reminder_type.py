"""merge the Part 3 re-budget and task-reminder heads

Revision ID: e7d3f1a90c48
Revises: d4a8c31e7b62, d4b9e63a08f7
Create Date: 2026-09-15 06:00:00

WHY THIS FILE EXISTS. Two migrations were written on 2026-09-12 against two
different parents and merged into main within hours of each other:

    c3f7b28d5e91 -> d4a8c31e7b62   Re-budget the early stages (PR #132)
    c3a8d51f7b62 -> d4b9e63a08f7   Register the task_reminder bell type (PR #131)

Neither is wrong and neither depends on the other -- one edits stage budgets,
the other inserts a notification type -- but together they leave the revision
tree with two heads. `backend-deploy.yml` runs `alembic upgrade head`
(SINGULAR, line 432), and alembic refuses to guess which head that means:

    Multiple head revisions are present for given argument 'head'

The migration task exits 255, the workflow correctly refuses to roll the new
image onto ECS ("ECS service will NOT be updated"), and EVERY backend deploy
stays blocked until the tree has one head again -- which is what happened to
run #190 on 2026-09-15.

This is an empty merge: it applies no DDL and no data change. It exists only
to join the two branches so `head` resolves to one revision again. Both
parents keep their own upgrade/downgrade; nothing here re-runs them.

Deliberately NOT fixed by changing the workflow to `upgrade heads` (plural).
That would paper over future forks by applying every branch in whatever order
alembic picks, which is exactly how two migrations that DO conflict end up
half-applied on production. A fork should be a loud failure and a deliberate
merge, which is this file.
"""

from typing import Sequence, Union

revision: str = "e7d3f1a90c48"
down_revision: Union[str, Sequence[str], None] = (
    "d4a8c31e7b62",
    "d4b9e63a08f7",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
