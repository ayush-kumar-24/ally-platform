"""New founders wait for approval before they can use the platform.

`founders.status` already existed with active/inactive/suspended/banned, an
admin endpoint to set it, and an audit trail behind it -- but nothing outside
the admin panel ever read it. Suspending or banning a founder changed a string
in a column and nothing else; they kept full access. The gate added in
`app/api/deps.py` is what makes every one of those states mean something, and
'pending' is the state new signups now start in.

Existing founders are deliberately untouched. They are 'active' and stay
'active': this migration adds a state, it does not put the current user base
behind an approval queue they never agreed to wait in.

'pending' is added rather than a separate `approved_at` column so there is one
answer to "may this person use the product", in one column, with one gate
reading it. Two sources would eventually disagree, and the disagreement would
be invisible until someone got in who should not have.
"""

from alembic import op

revision = "c1f5a83d70b2"
down_revision = "b4d927f1a6c8"
branch_labels = None
depends_on = None

_CONSTRAINT = "founders_status_check"
_OLD = ("active", "inactive", "suspended", "banned")
_NEW = ("pending", "active", "inactive", "suspended", "banned")


def _values(vals: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in vals)


def _swap(vals: tuple[str, ...]) -> None:
    op.execute(f"ALTER TABLE founders DROP CONSTRAINT IF EXISTS {_CONSTRAINT}")
    op.execute(
        f"ALTER TABLE founders ADD CONSTRAINT {_CONSTRAINT} "
        f"CHECK (status in ({_values(vals)}))"
    )


def upgrade() -> None:
    _swap(_NEW)


def downgrade() -> None:
    # Anyone still waiting would violate the narrower constraint. Approve them
    # rather than delete them: they are real signups, and the alternative to
    # letting them in is losing the row entirely. Downgrading this migration
    # means the gate is coming out too, so 'active' is what they would be.
    op.execute("UPDATE founders SET status = 'active' WHERE status = 'pending'")
    _swap(_OLD)
