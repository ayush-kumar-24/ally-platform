"""Rejoin the migration graph after two features branched from it in parallel.

NO SCHEMA CHANGE. This revision exists only to give the graph one head again.

Direct-signup capacity (c8f3a92e1d47, off a1f4c9b73e05) and the notification
email fan-out (c8f2b16d3a05, off b7e3a05c9f12) were written on separate branches
and merged into main within hours of each other. Neither is wrong and neither
touches the other's tables, but each named the head it saw when it was written,
so main ended up with two.

That is not a cosmetic problem. `alembic upgrade head` refuses to choose between
heads, and Backend CI's own safety check ("expected exactly 1 head") fails ahead
of it -- which is what took the backend deploy down: the deploy chains off that
workflow, so it was skipped rather than run, and every backend change merged
after the split sat undeployed on main while the frontend beside it shipped.

Merging is the whole fix. Ordering the two by hand instead would rewrite a
migration that has already run in production.
"""

from __future__ import annotations

revision = "d4a7e0c21b93"
down_revision = ("c8f3a92e1d47", "c8f2b16d3a05")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Nothing to do: both parents already carry their own schema changes."""


def downgrade() -> None:
    """Nothing to undo -- downgrading past this point re-splits the graph."""
