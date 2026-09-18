"""rejoin the industry branch

Revision ID: c1b8e05a37f4
Revises: a4e1f70c9d22, 62ebd946ebc0
Create Date: 2026-09-18 19:30

`62ebd946ebc0` (expand industries and add industry relevance) was authored
against `719a012becf1`, which by then already had a child -- so the two lines
are siblings and `alembic upgrade head` finds two heads and refuses. This is a
merge revision and nothing else; it has no upgrade body of its own.

WHY A MERGE AND NOT A REBASE. Rebasing would have been cleaner, and it was the
first choice. It is off the table because the effects of `62ebd946ebc0` are
ALREADY APPLIED to the production database -- verified 2026-09-18: the
`industry_relevance` columns exist on questions, problems and root_causes, and
`industries` holds all 30 rows. Rewriting the revision id of a migration a real
database has already run is how a schema and its history stop describing each
other.

WHAT THIS DOES NOT DO. It does not reconcile production's Alembic state. That
database reports `f8a3c26e4b91` -- a payments revision from an unmerged branch
-- and has never recorded `62ebd946ebc0` at all, so its history and its schema
already disagree independently of this file. Fixing that is a deployment task
with its own review; running this merge against production without it would
attempt `62ebd946ebc0`'s non-idempotent INSERT of industries 5-30 and fail on a
duplicate key.

For repository-managed databases (local, CI, a fresh environment) this makes
`alembic upgrade head` single-headed and complete again.
"""

from typing import Sequence, Union

revision: str = "c1b8e05a37f4"
down_revision: Union[str, Sequence[str], None] = ("a4e1f70c9d22", "62ebd946ebc0")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No-op: this revision exists to join two lineages, not to change schema."""


def downgrade() -> None:
    """No-op: splitting the lineages again is not a schema change either."""
