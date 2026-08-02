"""new table: revoked_tokens -- durable auth session revocation

InMemorySessionStore (app/core/auth/session_store.py) tracks revoked refresh-token
jtis in a process-local set: every logout / refresh-rotation is forgotten on
restart, and is invisible to any other worker process. A token revoked on one
worker still validates as live on another -- a real security gap, not just a UX
one (a "logged out" session, or a refresh token that should be one-time-use after
rotation, silently becomes valid again).

This is explicitly flagged in session_store.py's own docstring as needing
sign-off before adding a table -- that sign-off was given (see conversation
history), so this is the smallest table that closes the gap.

Not reusing the existing `sessions` table: that table belongs to the diagnosis
flow (question progress, risk scores, distress signals) and is unrelated to auth.

`expires_at` mirrors the JWT's own `exp` claim, so a revoked row can be pruned
once the token it revokes would have expired anyway (after that point the JWT
itself is rejected by signature/exp verification regardless of revocation state,
so keeping the row serves no purpose -- this bounds table growth without a cron).

Revision ID: f6b8c0d2e4a5
Revises: e5a7b9c1d3f4
Create Date: 2026-08-02 11:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f6b8c0d2e4a5"
down_revision: Union[str, Sequence[str], None] = "e5a7b9c1d3f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "revoked_tokens",
        sa.Column("jti", sa.String(length=64), primary_key=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_revoked_tokens_expires_at", "revoked_tokens", ["expires_at"])


def downgrade() -> None:
    op.drop_table("revoked_tokens")
