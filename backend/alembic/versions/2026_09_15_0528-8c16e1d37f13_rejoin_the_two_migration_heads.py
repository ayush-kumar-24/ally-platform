"""Rejoin the two migration heads.

The graph forked at b7e4f2a91c58 and never came back together:

    b7e4f2a91c58 ─┬─ c3f7b28d5e91 ── d4a8c31e7b62  (problems.dimension_code,
                  │                                 then the stage re-budget)
                  └─ c3a8d51f7b62 ── d4b9e63a08f7  (task reminder lead time,
                                                    then its notification type)

Two streams of work on the same day, each branched off the same revision, and
nothing merged them. The cost is not theoretical: `alembic upgrade head`
REFUSES to run against any database in that state --

    Multiple head revisions are present for given argument 'head'

-- so a deploy that migrates on boot fails, and a new environment cannot be
built at all. It was found running the migrations against an empty Postgres,
which is a thing nobody had done.

Empty on purpose. A merge revision carries no DDL; it exists so the two
branches have one descendant and `head` is unambiguous again. Both parents
keep their own upgrade/downgrade exactly as written.
"""

from typing import Sequence, Union

revision: str = "8c16e1d37f13"
down_revision: Union[str, Sequence[str], None] = ("d4a8c31e7b62", "d4b9e63a08f7")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No schema change: this revision only rejoins the graph."""


def downgrade() -> None:
    """No schema change: forking the graph again is what down_revision does."""
