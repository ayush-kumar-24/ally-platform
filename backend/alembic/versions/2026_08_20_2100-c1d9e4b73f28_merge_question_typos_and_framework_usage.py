"""Merge the two open heads: question-bank typo fix + framework_usage table

Revision ID: c1d9e4b73f28
Revises: b2d5f8a03c17, b3c9d15e8a47
Create Date: 2026-08-20 21:00:00

Two migrations were authored from different parents and both became heads:

    b3c9d15e8a47  fix "how well you X" -> "how well your X"   (down: f2a86d41c7b9)
    b2d5f8a03c17  add framework_usage table                   (down: a1c4e7f92d38)

That is not a cosmetic problem. The container start command is

    alembic upgrade head && uvicorn app.main:app ...

and `upgrade head` FAILS with "Multiple heads are present" when the tree has
branched, so the `&&` short-circuits and the app never starts. The next backend
deploy would have crash-looped on boot, with the schema untouched -- and the
typo fix, which only ever existed on the un-applied branch, would have stayed
unapplied indefinitely.

Merge-only revision: no schema change of its own, it just rejoins the branches
so `head` is single-valued again.
"""

from __future__ import annotations

from typing import Sequence, Union

revision: str = "c1d9e4b73f28"
down_revision: Union[str, Sequence[str], None] = ("b2d5f8a03c17", "b3c9d15e8a47")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Nothing to do -- this revision exists only to join the two branches."""


def downgrade() -> None:
    """Nothing to undo; splitting the heads again is not a meaningful operation."""
