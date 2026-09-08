"""Waitlist registrations -- the queue between "someone asked" and "they can log in".

Access to Ally is granted by approval, never by signing up: the Supabase
project has "Allow new users to sign up" switched OFF, and the frontend's
sendEmailOtp passes shouldCreateUser:false, so an address that has no
auth.users row simply cannot receive a login code. Until now the only way to
create that row was a human opening the Supabase dashboard, which meant the
approval decision lived nowhere, had no audit trail, and could not be capped.

This table is that missing middle. A registration arrives from the waitlist
site, sits here as `pending`, and an admin's approval is what creates the
Supabase identity and sends the founder their email.

WHY EMAIL IS UNIQUE AND CONFLICTS ARE SWALLOWED
The public endpoint must not become an account-existence oracle: someone who
can POST an address and tell "new" from "already there" apart can enumerate
who is on the founder list. So the insert is ON CONFLICT DO NOTHING and the
response is identical either way. The unique index is what makes that a single
statement rather than a check-then-insert race between two submissions of the
same form.

WHY THE ROW SURVIVES REJECTION
`rejected` is a state, not a delete. A rejected address that re-registers must
not quietly reappear as a fresh pending row -- the team already answered that
question, and re-asking it every week is how someone eventually gets approved
by accident.

RLS
Not founder-scoped: nobody in this table has a founder_id, and most never
will. What it holds is contact details for people who are not users, which is
exactly the shape of data that must not be reachable through Supabase's
auto-generated PostgREST API. So RLS is enabled with NO permissive policy for
public/authenticated -- deny-all through that surface -- following the
SELECT-only reasoning in 4aa14aee3a4e, one step stricter because there is no
legitimate direct-Supabase read of this table at all.

On RDS the `ally_app` role needs a policy or it would be locked out of a table
it must both write (the public form) and read (the panel). Its policy is
asymmetric on purpose: WITH CHECK (true) lets the unauthenticated form INSERT,
while USING (app.current_admin) means only a session that has declared itself
an admin actor can SELECT, UPDATE or DELETE. An anonymous POST can therefore
add a row and can never read one back -- including its own.
"""

from alembic import op
import sqlalchemy as sa

revision = "b8e3d5a91c47"
down_revision = "d7f4c2e91a63"
branch_labels = None
depends_on = None

_ALLY_APP = "ally_app"
_POLICY = "waitlist_admin_only"


def _ally_app_exists() -> bool:
    return bool(
        op.get_bind()
        .execute(sa.text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": _ALLY_APP})
        .scalar()
    )


def upgrade() -> None:
    op.create_table(
        "waitlist_registrations",
        sa.Column("registration_id", sa.Integer(), autoincrement=True, nullable=False),
        # Lower-cased by the application before it ever reaches here, so the
        # unique index below is genuinely one-row-per-person rather than
        # per-capitalisation. See app/services/waitlist.py.
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("company", sa.String(length=200), nullable=True),
        sa.Column("role_title", sa.String(length=120), nullable=True),
        sa.Column("stage", sa.String(length=60), nullable=True),
        # Whatever the form asked ("what are you building", "why Ally"). Free
        # text, because the waitlist site owns its own questions and this table
        # should not need a migration every time it rewords one.
        sa.Column("note", sa.Text(), nullable=True),
        # Which form/campaign sent them, for the team's own attribution.
        sa.Column("source", sa.String(length=60), nullable=True),
        sa.Column("status", sa.String(length=12), server_default=sa.text("'pending'"),
                  nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        # The panel admin who approved or rejected. Deliberately not a FK: an
        # admin is an entry in GOXL_ADMIN_PANEL_USERS resolved to a founder row,
        # and a decision must stay legible after that founder row is gone.
        sa.Column("decided_by_admin_id", sa.Integer(), nullable=True),
        sa.Column("decided_by_email", sa.String(length=255), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        # The Supabase auth.users id created at approval. Its presence is what
        # "this person can actually log in" means -- approval alone does not,
        # because creating the identity is a network call that can fail after
        # the row is already marked approved.
        sa.Column("auth_user_id", sa.UUID(), nullable=True),
        sa.Column("access_granted_at", sa.DateTime(timezone=True), nullable=True),
        # Separate from access_granted_at: the identity can exist while the
        # email failed to send, and that founder needs chasing, not re-approving.
        sa.Column("approval_email_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.CheckConstraint("status IN ('pending', 'approved', 'rejected')",
                           name="waitlist_registrations_status_check"),
        sa.PrimaryKeyConstraint("registration_id", name="waitlist_registrations_pkey"),
    )
    op.create_index("waitlist_registrations_email_key", "waitlist_registrations",
                    ["email"], unique=True)
    # The panel's default view is "pending, oldest first" -- the queue order is
    # the order people asked, so the person who has waited longest is on top.
    op.create_index("idx_waitlist_status_created", "waitlist_registrations",
                    ["status", "created_at"])

    # Deny-all through PostgREST: enabled, with no policy granting anyone
    # anything. See the module docstring.
    op.execute('ALTER TABLE public."waitlist_registrations" ENABLE ROW LEVEL SECURITY')

    if _ally_app_exists():
        op.execute(f'DROP POLICY IF EXISTS "{_POLICY}" ON public."waitlist_registrations"')
        admin = (
            "COALESCE(NULLIF(current_setting('app.current_admin', true), '')::boolean, false)"
        )
        op.execute(
            f'CREATE POLICY "{_POLICY}" ON public."waitlist_registrations" '
            f"AS PERMISSIVE FOR ALL TO {_ALLY_APP} "
            # USING gates SELECT/UPDATE/DELETE; WITH CHECK gates the INSERT the
            # public form makes with no admin context at all.
            f"USING ({admin}) WITH CHECK (true)"
        )
        op.execute(
            'GRANT SELECT, INSERT, UPDATE, DELETE ON public."waitlist_registrations" '
            f"TO {_ALLY_APP}"
        )
        op.execute(
            "GRANT USAGE, SELECT ON SEQUENCE "
            f"waitlist_registrations_registration_id_seq TO {_ALLY_APP}"
        )


def downgrade() -> None:
    op.drop_index("idx_waitlist_status_created", table_name="waitlist_registrations")
    op.drop_index("waitlist_registrations_email_key", table_name="waitlist_registrations")
    op.drop_table("waitlist_registrations")
