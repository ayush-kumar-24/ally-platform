"""Launch becomes a small allowance instead of a one-way door.

The gate shipped with `launched` as a terminal state, on the reasoning that a
public go-live happens once. That is true of the real one and false of every
rehearsal before it -- and the first thing that happened in production was a
trial launch that could not be undone. A ceremony nobody may practise is a
ceremony performed for the first time in front of an audience.

So the platform may now be launched `max_launches` times in its lifetime, and
`reset` closes it again between them. The last one is final.

WHY A BUDGET AND NOT A TOGGLE
An un-launch with no limit is a toggle, and a toggle eventually gets pressed
on a platform full of founders mid-diagnosis -- which is exactly what the
terminal state was protecting against. Counting the launches buys the
rehearsals and still guarantees the launch everybody remembers cannot be taken
back, because by then there is nothing left to spend.

The ceiling lives in this column rather than in code or an admin endpoint on
purpose. An allowance the panel can raise is not an allowance; raising it has
to be a database change somebody makes deliberately.

WHY THE COUNTER IS A COLUMN AND NOT DERIVED FROM THE AUDIT LOG
Both record launches, but they answer to different masters. The audit trail is
evidence for humans and may be pruned, exported or rotated; a safety limit
that stopped working because somebody archived old audit rows would fail in
the most dangerous direction, silently handing back a fresh allowance.

BACKFILL: AN ALREADY-LAUNCHED ROW COUNTS AS ONE
A platform sitting in `launched` when this runs got there by somebody pressing
the button, so it starts at 1, not 0. Seeding 0 would hand back a full
allowance and quietly make the trial free -- the accounting would say three
launches remained after one had already happened. Every other state starts at
0, which is simply the truth for a platform that has never opened.
"""

from alembic import op
import sqlalchemy as sa

revision = "f6c3b58e2d94"
down_revision = "e5b2d47a91c3"
branch_labels = None
depends_on = None

_DEFAULT_MAX_LAUNCHES = 3


def upgrade() -> None:
    op.add_column(
        "launch_state",
        sa.Column("launch_count", sa.Integer(), server_default=sa.text("0"),
                  nullable=False),
    )
    op.add_column(
        "launch_state",
        sa.Column("max_launches", sa.Integer(),
                  server_default=sa.text(str(_DEFAULT_MAX_LAUNCHES)), nullable=False),
    )

    # See BACKFILL above: the trial launch already spent one.
    op.execute(
        'UPDATE public."launch_state" SET launch_count = 1 '
        "WHERE state = 'launched' AND launch_count = 0"
    )

    op.create_check_constraint(
        "launch_state_count_nonneg", "launch_state", "launch_count >= 0")
    # Upper bound as well as lower: the counter is a safety limit, and a limit
    # that can be exceeded is not one. `launch_count <= max_launches` is the
    # invariant the reset refusal depends on, so the database asserts it too
    # rather than trusting every future writer to.
    op.create_check_constraint(
        "launch_state_count_within_allowance", "launch_state",
        "launch_count <= max_launches")
    # Deliberately small. Nothing here should be able to set the ceiling to a
    # number that makes launching effectively unlimited -- at that point the
    # allowance stops being a safety property and the final launch stops being
    # final.
    op.create_check_constraint(
        "launch_state_max_launches_bounds", "launch_state",
        "max_launches BETWEEN 1 AND 10")


def downgrade() -> None:
    for name in ("launch_state_max_launches_bounds",
                 "launch_state_count_within_allowance",
                 "launch_state_count_nonneg"):
        op.drop_constraint(name, "launch_state", type_="check")
    op.drop_column("launch_state", "max_launches")
    op.drop_column("launch_state", "launch_count")
