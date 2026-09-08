"""Slot openings -- the team deciding, from the panel, how many people come in.

Until now the size of the founder list was `WAITLIST_APPROVAL_CAP`, an
environment variable. Letting in ten more people meant editing a task
definition and waiting for a deploy, so in practice it meant asking whoever
owns the pipeline. That is the wrong shape for a decision the team makes while
reading the queue.

Each row here is one act of opening slots: how many, by whom, when, and how
many of them actually turned into approvals. The effective cap is the
environment value plus the sum of this table, so the env var keeps its meaning
as the starting size rather than being overwritten by a hand-set number that
the next deploy would silently revert -- the same failure that put
ADAPTIVE_QUESTIONS off in production.

APPEND-ONLY, AND WHY
No UPDATE of a single "current cap" row. Two admins opening slots at the same
moment would race on that row and one opening would vanish; two INSERTs cannot
lose each other. It also means the panel can always answer "who let these
people in, and when", which a mutable counter cannot.

`approved_count` is written after the approvals run and may be lower than
`slots_opened` -- the queue can be shorter than the number opened, or an
identity call can fail. The unused capacity stays available, which is why it is
recorded rather than inferred.
"""

from alembic import op
import sqlalchemy as sa

revision = "a4d7c6e2b915"
down_revision = "c7e4b19d5a20"
branch_labels = None
depends_on = None

_ALLY_APP = "ally_app"
_POLICY = "waitlist_slots_admin_only"


def _ally_app_exists() -> bool:
    return bool(
        op.get_bind()
        .execute(sa.text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": _ALLY_APP})
        .scalar()
    )


def upgrade() -> None:
    op.create_table(
        "waitlist_slot_openings",
        sa.Column("opening_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("slots_opened", sa.Integer(), nullable=False),
        # Filled in after the approvals run. Lower than slots_opened when the
        # queue was shorter, or when an identity call failed.
        sa.Column("approved_count", sa.Integer(), server_default=sa.text("0"),
                  nullable=False),
        # Same reasoning as waitlist_registrations.decided_by_admin_id: not a
        # FK, because an admin is an entry in GOXL_ADMIN_PANEL_USERS and this
        # record must stay legible after their founder row is gone.
        sa.Column("opened_by_admin_id", sa.Integer(), nullable=True),
        sa.Column("opened_by_email", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("slots_opened > 0", name="waitlist_slot_openings_positive"),
        sa.CheckConstraint("approved_count >= 0",
                           name="waitlist_slot_openings_approved_nonneg"),
        sa.PrimaryKeyConstraint("opening_id", name="waitlist_slot_openings_pkey"),
    )

    # Deny-all through PostgREST, exactly as waitlist_registrations (b8e3d5a91c47):
    # nobody in this table is a founder, and none of it is a legitimate direct
    # Supabase read.
    op.execute('ALTER TABLE public."waitlist_slot_openings" ENABLE ROW LEVEL SECURITY')

    if _ally_app_exists():
        op.execute(f'DROP POLICY IF EXISTS "{_POLICY}" ON public."waitlist_slot_openings"')
        admin = (
            "COALESCE(NULLIF(current_setting('app.current_admin', true), '')::boolean, false)"
        )
        # Stricter than the registrations policy: that one takes WITH CHECK
        # (true) because the public form inserts with no admin context. Nothing
        # unauthenticated ever writes here, so both sides demand an admin.
        op.execute(
            f'CREATE POLICY "{_POLICY}" ON public."waitlist_slot_openings" '
            f"AS PERMISSIVE FOR ALL TO {_ALLY_APP} "
            f"USING ({admin}) WITH CHECK ({admin})"
        )
        op.execute(
            'GRANT SELECT, INSERT, UPDATE ON public."waitlist_slot_openings" '
            f"TO {_ALLY_APP}"
        )
        op.execute(
            "GRANT USAGE, SELECT ON SEQUENCE "
            f"waitlist_slot_openings_opening_id_seq TO {_ALLY_APP}"
        )


def downgrade() -> None:
    op.execute(f'DROP POLICY IF EXISTS "{_POLICY}" ON public."waitlist_slot_openings"')
    op.drop_table("waitlist_slot_openings")
