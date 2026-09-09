"""The launch gate's single row -- the go-live moment, as state rather than a deploy.

Opening the platform to everyone used to have no representation at all: it
would have been a deploy, or an environment variable, done by whoever owns the
pipeline. This makes it a thing the team does from the panel, at a moment they
choose, in front of whoever is watching -- and a thing that is recorded
afterwards.

ONE ROW, SEEDED HERE
There is one launch, so there is one row, and its id is the constant
app.launch.service.STATE_ID rather than something a caller passes in. An
endpoint that could address "launch state 2" would be an endpoint that could
launch the wrong thing.

SEEDED `open`, NOT `armed`, AND THIS IS THE IMPORTANT PART
`open` means "no gate" -- the platform behaves exactly as it did before this
table existed. Seeding `armed` would put a holding screen in front of a live
platform the instant this migration ran, signing every founder mid-diagnosis
out of a product that was working a second earlier, as a side effect of a
deploy nobody thought was risky. The gate closes when a super admin
deliberately arms it from the panel, and never because a migration ran.

WHY THE COUNTDOWN DEADLINE IS STORED
`countdown_ends_at` is what makes every viewer's countdown the same countdown,
and what makes the launch button refuse to work before the abort window has
actually elapsed. A frontend animation can do neither: laptops in one room
disagree about the time by seconds, and an animation is skipped by a refresh.

`launched_at` / `launched_by` are the record of the one-time event. Nothing in
the application writes them twice -- LaunchService.launch is idempotent, not
repeatable -- so a second press cannot rewrite who launched or when.
"""

from alembic import op
import sqlalchemy as sa

revision = "e5b2d47a91c3"
down_revision = "d4a7e0c21b93"
branch_labels = None
depends_on = None

_ALLY_APP = "ally_app"
_READ_POLICY = "launch_state_readable"
_WRITE_POLICY = "launch_state_admin_writes"


def _ally_app_exists() -> bool:
    return bool(
        op.get_bind()
        .execute(sa.text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": _ALLY_APP})
        .scalar()
    )


def upgrade() -> None:
    op.create_table(
        "launch_state",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("state", sa.String(length=20), server_default=sa.text("'open'"),
                  nullable=False),
        sa.Column("countdown_seconds", sa.Integer(), server_default=sa.text("10"),
                  nullable=False),
        sa.Column("countdown_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("countdown_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("launched_at", sa.DateTime(timezone=True), nullable=True),
        # Not an FK to founders, for the same reason as
        # waitlist_registrations.decided_by_admin_id: an admin is an entry in
        # GOXL_ADMIN_PANEL_USERS, and this record has to stay legible after
        # their founder row is gone. Losing the name of who launched the
        # platform to an unrelated account deletion is not acceptable.
        sa.Column("launched_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        # The four states named in one place the application cannot drift
        # from. A typo'd state would otherwise read as "unknown" and, because
        # this gate fails open, would silently open the platform.
        sa.CheckConstraint(
            "state IN ('open', 'armed', 'counting', 'launched')",
            name="launch_state_known_state"),
        # A countdown with no deadline is a countdown nobody can finish and
        # the launch button would never unlock.
        sa.CheckConstraint(
            "state <> 'counting' OR countdown_ends_at IS NOT NULL",
            name="launch_state_counting_has_deadline"),
        sa.CheckConstraint(
            "countdown_seconds BETWEEN 3 AND 300",
            name="launch_state_countdown_bounds"),
        # The singleton, enforced by the database rather than by everyone
        # remembering to pass id=1.
        sa.CheckConstraint("id = 1", name="launch_state_singleton"),
        sa.PrimaryKeyConstraint("id", name="launch_state_pkey"),
    )

    op.execute(
        "INSERT INTO public.\"launch_state\" (id, state, countdown_seconds) "
        "VALUES (1, 'open', 10) ON CONFLICT (id) DO NOTHING"
    )

    op.execute('ALTER TABLE public."launch_state" ENABLE ROW LEVEL SECURITY')

    if _ally_app_exists():
        op.execute(f'DROP POLICY IF EXISTS "{_READ_POLICY}" ON public."launch_state"')
        op.execute(f'DROP POLICY IF EXISTS "{_WRITE_POLICY}" ON public."launch_state"')
        # READ IS OPEN TO THE APP, unlike every other table added recently.
        # GET /launch/status is unauthenticated by design -- the visitors who
        # most need to know whether the platform is open are the ones who
        # cannot sign in yet -- so the request carries neither a founder nor
        # an admin RLS context. A policy requiring either would make the
        # holding screen unable to read the state it exists to display. The
        # row holds no founder data: a state name, a countdown length and two
        # timestamps.
        op.execute(
            f'CREATE POLICY "{_READ_POLICY}" ON public."launch_state" '
            f"AS PERMISSIVE FOR SELECT TO {_ALLY_APP} USING (true)"
        )
        admin = (
            "COALESCE(NULLIF(current_setting('app.current_admin', true), '')::boolean, false)"
        )
        # Writing is another matter entirely: this is the row that decides
        # whether the platform is open, so both sides demand admin context.
        op.execute(
            f'CREATE POLICY "{_WRITE_POLICY}" ON public."launch_state" '
            f"AS PERMISSIVE FOR UPDATE TO {_ALLY_APP} "
            f"USING ({admin}) WITH CHECK ({admin})"
        )
        # No INSERT grant and no INSERT policy: the one row is seeded above
        # and the application only ever updates it. A second row cannot be
        # created even by an admin -- the singleton check would reject it
        # anyway, and this way the attempt fails before it gets that far.
        op.execute(f'GRANT SELECT, UPDATE ON public."launch_state" TO {_ALLY_APP}')


def downgrade() -> None:
    op.execute(f'DROP POLICY IF EXISTS "{_READ_POLICY}" ON public."launch_state"')
    op.execute(f'DROP POLICY IF EXISTS "{_WRITE_POLICY}" ON public."launch_state"')
    op.drop_table("launch_state")
