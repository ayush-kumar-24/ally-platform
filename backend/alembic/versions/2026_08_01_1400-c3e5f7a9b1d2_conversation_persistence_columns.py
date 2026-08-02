"""conversations: durable-persistence columns for the chat resume fix

Adds what the domain Conversation needs that the table didn't yet carry:
  - external_id: the string id the ConversationService already mints (uuid hex) --
    the domain layer identifies conversations by this, not the internal integer PK.
  - unread_count, token_stats, metadata: fields the service round-trips on every
    write via replace_conversation(); without a column they'd be silently dropped.
  - status CHECK extended to allow 'deleted' (soft-delete state the domain already
    has; the DB only allowed active/completed/archived).

messages needs no new columns: its existing `id` (uuid) becomes the domain
message_id, and its existing `metadata` jsonb carries `important` / the token-usage
split. Both tables are empty in production, so these are safe additive changes.

Revision ID: c3e5f7a9b1d2
Revises: b2c4d6e8f0a1
Create Date: 2026-08-01 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c3e5f7a9b1d2"
down_revision: Union[str, Sequence[str], None] = "b2c4d6e8f0a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("external_id", sa.String(length=64), nullable=True))
    op.add_column(
        "conversations",
        sa.Column("unread_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "conversations",
        sa.Column("token_stats", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "conversations",
        sa.Column("metadata", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
    )
    # Backfill any pre-existing rows (none in production today) before enforcing
    # NOT NULL + UNIQUE, so this migration is safe to run even if that changes.
    op.execute("UPDATE conversations SET external_id = 'legacy-' || conversation_id::text WHERE external_id IS NULL")
    op.alter_column("conversations", "external_id", nullable=False)
    op.create_unique_constraint("conversations_external_id_key", "conversations", ["external_id"])
    op.create_index("ix_conversations_external_id", "conversations", ["external_id"])

    op.drop_constraint("conversations_status_check", "conversations", type_="check")
    op.create_check_constraint(
        "conversations_status_check",
        "conversations",
        "status IN ('active','completed','archived','deleted')",
    )


def downgrade() -> None:
    op.drop_constraint("conversations_status_check", "conversations", type_="check")
    op.create_check_constraint(
        "conversations_status_check",
        "conversations",
        "status IN ('active','completed','archived')",
    )
    op.drop_index("ix_conversations_external_id", table_name="conversations")
    op.drop_constraint("conversations_external_id_key", "conversations", type_="unique")
    op.drop_column("conversations", "metadata")
    op.drop_column("conversations", "token_stats")
    op.drop_column("conversations", "unread_count")
    op.drop_column("conversations", "external_id")
