"""Rejoin the heads after main moved underneath this branch.

    ... ── a1c7e4f93b25   (this branch: reconcile the schema drift)
    ... ── c8e5a1d40f73   (main: hold the team's own accounts at Pro)

Two heads again, and for the ordinary reason rather than a mistake: this
branch was cut before `c8e5a1d40f73` landed on main, and both sides added a
migration. Neither is wrong; they simply have no common descendant.

CI caught it, and it is worth saying how, because it is not the obvious way.
The branch alone has exactly one head -- `alembic heads` run here passes.
GitHub Actions checks out the MERGE of the branch and its base, so the second
head only exists in the thing that will actually be merged. A migration graph
can therefore be sound on both sides and forked in the result, which is the
state that matters and the only place it is visible.

    Unsafe Alembic graph: expected exactly 1 head, got
    ['c8e5a1d40f73', 'a1c7e4f93b25']

That check is doing real work. `alembic upgrade head` REFUSES to run against a
forked graph -- "Multiple head revisions are present for given argument
'head'" -- so the deploy workflow's migration task would fail, and with it the
deploy, before the service was touched.

Empty on purpose. A merge revision carries no DDL; it exists so the two
branches have one descendant and `head` is unambiguous again. Both parents
keep their own upgrade/downgrade exactly as written.
"""

from typing import Sequence, Union

revision: str = "e9b4d72c5a18"
down_revision: Union[str, Sequence[str], None] = ("a1c7e4f93b25", "c8e5a1d40f73")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No schema change: this revision only rejoins the graph."""


def downgrade() -> None:
    """No schema change: forking the graph again is what down_revision does."""
