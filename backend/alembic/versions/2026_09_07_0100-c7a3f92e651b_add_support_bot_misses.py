"""Keep the questions the help bot could not answer.

WHAT WAS BEING THROWN AWAY. When the support bot has no answer it builds a
reply, returns `reason="no_match"`, and writes nothing -- not a row, not even a
log line. So the single most valuable dataset the bot produces, the list of
questions founders actually ask that our help content does not cover, was
discarded on every miss.

That list is what tells us which answer to write next. Without it the help
content can only ever be improved by guessing at what founders want, which is
how a 300-question bank ends up missing the ten questions people really ask.

WHY A TABLE AND NOT A LOG LINE. A log line is searchable by whoever has log
access and nobody else, and it ages out. This has to be readable by the person
who writes the help answers, in the admin panel, next to everything else the
team reviews.

WHAT IT DOES NOT STORE. No answer, no model output, no conversation -- just what
was asked, why we could not answer it, and when. `founder_id` is kept so a
recurring asker can be recognised and, if their question is worth a real reply,
followed up. It is deliberately NOT a support ticket: nobody is promised an
answer here, and the founder-facing escalation path is unchanged.

RLS. Founder-scoped like every other table carrying founder_id, with the same
policy the estate uses -- own rows, or an admin session. A question a founder
typed into a help box is their data even though we are reading it in aggregate.

Revision ID: c7a3f92e651b
Revises: b4e7d21a9c68
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision = "c7a3f92e651b"
down_revision = "b4e7d21a9c68"
branch_labels = None
depends_on = None

TABLE = "support_bot_misses"
POLICY_NAME = "ally_founder_isolation"
ALLY_APP_ROLE = "ally_app"


def _ally_app_exists() -> bool:
    """Whether the RDS-only `ally_app` runtime role exists on this target.
    Duplicated per-migration on purpose -- see the note in 7c4f0f1a9d2e."""
    return bool(
        op.get_bind()
        .execute(text("SELECT 1 FROM pg_roles WHERE rolname = :role"),
                 {"role": ALLY_APP_ROLE})
        .scalar()
    )


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("miss_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("founder_id", sa.Integer(), nullable=False),
        # 2000 to match the support endpoint's own cap on a question. Anything
        # longer was already rejected before it reached the bot.
        sa.Column("question", sa.Text(), nullable=False),
        # Which failure this was: no_match, content_unavailable, and room for
        # whatever the service grows next. Not constrained by a CHECK -- a new
        # reason string must never be able to break the write and cost us the
        # founder's reply, which is the whole reason this table is best-effort.
        sa.Column("reason", sa.String(length=40), nullable=False),
        sa.Column("asked_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["founder_id"], ["founders.founder_id"],
                                name=f"{TABLE}_founder_id_fkey", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("miss_id", name=f"{TABLE}_pkey"),
    )
    # The admin page reads newest-first and nothing else, so one index, matching
    # that. Added now rather than "when it gets slow": this table only grows.
    op.create_index(f"ix_{TABLE}_asked_at", TABLE, ["asked_at"], unique=False)

    if not _ally_app_exists():
        # Local/Supabase targets have no ally_app role, and `CREATE POLICY ... TO
        # ally_app` errors there. Same guard every RLS migration in this repo
        # carries -- see d91c6e4b72aa.
        print(f"ally_app role absent -- skipping RLS policy on {TABLE}")
        return

    predicate = (
        "(founder_id = public.get_founder_id()) OR "
        "(COALESCE(NULLIF(current_setting('app.current_admin', true), '')::boolean, false))"
    )
    op.execute(f'ALTER TABLE public."{TABLE}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'DROP POLICY IF EXISTS "{POLICY_NAME}" ON public."{TABLE}"')
    op.execute(
        f'CREATE POLICY "{POLICY_NAME}" ON public."{TABLE}" '
        f"AS PERMISSIVE FOR ALL TO {ALLY_APP_ROLE} "
        f"USING ({predicate}) WITH CHECK ({predicate})"
    )
    op.execute(f'GRANT SELECT, INSERT ON public."{TABLE}" TO {ALLY_APP_ROLE}')
    op.execute(
        f'GRANT USAGE, SELECT ON SEQUENCE public."{TABLE}_miss_id_seq" TO {ALLY_APP_ROLE}'
    )


def downgrade() -> None:
    op.drop_index(f"ix_{TABLE}_asked_at", table_name=TABLE)
    op.drop_table(TABLE)
