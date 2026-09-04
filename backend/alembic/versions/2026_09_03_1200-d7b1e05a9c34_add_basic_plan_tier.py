"""Allow the Rs 199 'basic' plan tier.

`founders.plan_type` is guarded by a CHECK constraint listing the tiers by name,
so adding a tier to the catalog is not enough -- every write of 'basic' would be
rejected by the database until this runs.

'enterprise' stays in the list even though no PlanTier member matches it. It was
already permitted, rows may carry it, and dropping a value from a CHECK is what
turns a widening migration into a failing one. `get_plan()` resolves it to Free,
so an unknown-but-permitted value grants the least rather than the most.
"""

from alembic import op

revision = "d7b1e05a9c34"
down_revision = "c6a4e83f19d7"
branch_labels = None
depends_on = None

_CONSTRAINT = "founders_plan_type_check"
_OLD = ("free", "starter", "pro", "enterprise")
_NEW = ("free", "basic", "starter", "pro", "enterprise")


def _values(tiers: tuple[str, ...]) -> str:
    return ", ".join(f"'{t}'::character varying" for t in tiers)


def _swap(tiers: tuple[str, ...]) -> None:
    # IF EXISTS so a database provisioned from a snapshot that predates the
    # constraint does not fail here; the ADD below is what actually matters.
    op.execute(f"ALTER TABLE founders DROP CONSTRAINT IF EXISTS {_CONSTRAINT}")
    op.execute(
        f"ALTER TABLE founders ADD CONSTRAINT {_CONSTRAINT} "
        f"CHECK (plan_type::text = ANY (ARRAY[{_values(tiers)}]::text[]))"
    )


def upgrade() -> None:
    _swap(_NEW)


def downgrade() -> None:
    # Anyone already on Basic would violate the narrower constraint, so move them
    # to Free first. Downgrading the schema must not strand a paying founder in a
    # row the database will not accept -- and Free is the fail-closed direction.
    op.execute("UPDATE founders SET plan_type = 'free' WHERE plan_type = 'basic'")
    _swap(_OLD)
