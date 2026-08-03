"""add admin panel: founder admin columns, credit ledger, persistent audit log

Revision ID: e5f1a93c6d42
Revises: d4e0f82a5b31
Create Date: 2026-08-02 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f1a93c6d42'
down_revision: Union[str, Sequence[str], None] = 'd4e0f82a5b31'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Three additions, all additive.

    1. Columns the admin panel needs that `founders` did not have: the searchable
       fields (phone, business_name), lifecycle status, activity tracking, the
       admin-only note field, and the credit balance.

       `credits_balance` is a CACHE of the ledger, not the source of truth -- the
       ledger in credit_transactions is authoritative. Keeping a column avoids
       summing the whole ledger on every list query, and every write goes through
       the service that updates both in one transaction.

    2. credit_transactions -- the append-only ledger. balance_before/after are
       stored on each row so a balance can be reconstructed and audited without
       replaying arithmetic, and so a mismatch is detectable.

    3. admin_audit_log -- persistent, immutable. The existing admin audit was
       in-memory, which means every restart erased it; an audit trail that does
       not survive a restart is not an audit trail.
    """
    # --- 1. founders: admin/searchable columns ---------------------------
    op.add_column("founders", sa.Column("phone", sa.String(length=20), nullable=True))
    op.add_column("founders", sa.Column("business_name", sa.String(length=200), nullable=True))
    op.add_column("founders", sa.Column("status", sa.String(length=20), nullable=False,
                                        server_default="active"))
    op.add_column("founders", sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("founders", sa.Column("admin_notes", sa.Text(), nullable=True))
    op.add_column("founders", sa.Column("credits_balance", sa.Integer(), nullable=False,
                                        server_default="0"))
    op.create_index("ix_founders_status", "founders", ["status"])
    op.create_index("ix_founders_phone", "founders", ["phone"])
    op.create_index("ix_founders_business_name", "founders", ["business_name"])
    op.create_check_constraint(
        "founders_status_check", "founders",
        "status in ('active','inactive','suspended','banned')",
    )
    # A balance can never go below zero -- enforced at the database as well as in
    # the service, so no future code path (or manual UPDATE) can breach it.
    op.create_check_constraint(
        "founders_credits_non_negative", "founders", "credits_balance >= 0",
    )

    # --- 2. credit ledger ------------------------------------------------
    op.create_table(
        "credit_transactions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(),
                  sa.ForeignKey("founders.founder_id", ondelete="CASCADE"), nullable=False),
        sa.Column("admin_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("balance_before", sa.Integer(), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.CheckConstraint("type in ('add','remove','set','bonus')",
                           name="credit_transactions_type_check"),
        sa.CheckConstraint("balance_after >= 0", name="credit_transactions_after_non_negative"),
    )
    op.create_index("ix_credit_transactions_user_id", "credit_transactions", ["user_id"])
    op.create_index("ix_credit_transactions_user_created",
                    "credit_transactions", ["user_id", "created_at"])

    # --- 3. persistent admin audit log -----------------------------------
    op.create_table(
        "admin_audit_log",
        sa.Column("event_id", sa.String(length=64), primary_key=True),
        sa.Column("admin_id", sa.Integer(), nullable=False),
        sa.Column("admin_email", sa.String(length=200), nullable=False),
        sa.Column("admin_role", sa.String(length=20), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("resource", sa.String(length=120), nullable=False),
        sa.Column("target_user_id", sa.Integer(), nullable=True),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),   # 45 = IPv6 max
        sa.Column("result", sa.String(length=20), nullable=False, server_default="success"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("ix_admin_audit_log_timestamp", "admin_audit_log", ["timestamp"])
    op.create_index("ix_admin_audit_log_admin_id", "admin_audit_log", ["admin_id"])
    op.create_index("ix_admin_audit_log_target", "admin_audit_log", ["target_user_id"])


def downgrade() -> None:
    op.drop_table("admin_audit_log")
    op.drop_table("credit_transactions")
    op.drop_constraint("founders_credits_non_negative", "founders", type_="check")
    op.drop_constraint("founders_status_check", "founders", type_="check")
    op.drop_index("ix_founders_business_name", table_name="founders")
    op.drop_index("ix_founders_phone", table_name="founders")
    op.drop_index("ix_founders_status", table_name="founders")
    for col in ("credits_balance", "admin_notes", "last_active_at",
                "status", "business_name", "phone"):
        op.drop_column("founders", col)
