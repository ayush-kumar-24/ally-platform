"""Direct-signup capacity -- how many of the founder's OWN slots are open right
now for a stranger to sign in and get an account on the spot, no approval.

Registration was opened at the client level (see the frontend's own history):
`sendEmailOtp` now asks Supabase to create the user, so a code is the only
thing between a stranger and an account. That is exactly right for someone
inside the batch the team just opened -- and exactly wrong for someone
outside it, because nothing before this migration stopped counting.

THE SHAPE OF THE FEATURE THIS SERVES
Opening N slots (see waitlist.py's open_slots) does two things now, not one:
it drains the pending queue oldest-first as it always did, and whatever of N
is left over becomes direct-signup capacity -- places a stranger can fill by
signing in, not by waiting for an admin. The moment that capacity reaches
zero, a new arrival goes back to the queue (register()), exactly as if
sign-ups had never opened. The landing page's own "Register" vs "Log in"
button reads this table's remaining count (via a public endpoint) to know
which one to show; this table is the single fact both the frontend's button
and the backend's enforcement read, so they cannot disagree.

ENFORCEMENT LIVES IN THE BACKEND, NOT THE BUTTON
A landing-page button is a convenience, not a boundary -- the login page's
own URL is reachable directly, with no button in front of it. The actual gate
is in app/services/provisioning.py, at the one place every brand-new identity
passes through before it gets a founders row: SELECT ... FOR UPDATE against
this table's single row, inside the same transaction as the row it may or may
not create, so two people signing in at the exact moment one slot remains
cannot both get through.

A SINGLETON, LIKE waitlist_registrations HAS NO EQUIVALENT FOR
Every other waitlist table is a ledger (one row per registration, one row per
opening). This is deliberately not: there is exactly one number that matters
right now -- how many direct slots remain -- and a ledger of every increment
and decrement would answer a question nobody asks. `id boolean primary key
default true check (id)` is the standard single-row-table shape: the CHECK
makes a second row a constraint violation, not a business rule an admin could
forget.
"""

from alembic import op
import sqlalchemy as sa

revision = "c8f3a92e1d47"
down_revision = "a1f4c9b73e05"
branch_labels = None
depends_on = None

_ALLY_APP = "ally_app"
_POLICY = "direct_signup_capacity_app_only"


def _ally_app_exists() -> bool:
    return bool(
        op.get_bind()
        .execute(sa.text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": _ALLY_APP})
        .scalar()
    )


def upgrade() -> None:
    op.create_table(
        "direct_signup_capacity",
        sa.Column("id", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        # How many strangers may still sign in and get an account with no
        # queue and no approval, right now. Decremented inside the same
        # transaction as the founders row it gates; see provisioning.py.
        sa.Column("remaining", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("id", name="direct_signup_capacity_singleton"),
        sa.CheckConstraint("remaining >= 0", name="direct_signup_capacity_nonneg"),
        sa.PrimaryKeyConstraint("id", name="direct_signup_capacity_pkey"),
    )
    op.execute(
        "INSERT INTO direct_signup_capacity (id, remaining) VALUES (true, 0)"
    )

    # Deny-all through PostgREST, same as every other table this backend owns
    # end to end -- nothing here is a legitimate direct-Supabase read either.
    op.execute('ALTER TABLE public."direct_signup_capacity" ENABLE ROW LEVEL SECURITY')

    if _ally_app_exists():
        op.execute(f'DROP POLICY IF EXISTS "{_POLICY}" ON public."direct_signup_capacity"')
        # Unlike waitlist_slot_openings (admin-only) or waitlist_registrations
        # (admin read, public insert), this table is read and written during
        # an ORDINARY FOUNDER'S OWN sign-in -- there is no admin actor and no
        # founder_id to scope it to, only a single shared counter every
        # connection of this one app role must be able to touch. Fully open
        # to ally_app; nothing behind PostgREST reaches it regardless.
        op.execute(
            f'CREATE POLICY "{_POLICY}" ON public."direct_signup_capacity" '
            f"AS PERMISSIVE FOR ALL TO {_ALLY_APP} USING (true) WITH CHECK (true)"
        )
        op.execute(
            'GRANT SELECT, INSERT, UPDATE ON public."direct_signup_capacity" '
            f"TO {_ALLY_APP}"
        )


def downgrade() -> None:
    op.execute(f'DROP POLICY IF EXISTS "{_POLICY}" ON public."direct_signup_capacity"')
    op.drop_table("direct_signup_capacity")
