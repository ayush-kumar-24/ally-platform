"""credit expiry buckets, feature flags, broadcasts

Revision ID: f6a2b04d7e53
Revises: e5f1a93c6d42
Create Date: 2026-08-02 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f6a2b04d7e53'
down_revision: Union[str, Sequence[str], None] = 'e5f1a93c6d42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Credits become two buckets; plus feature flags and broadcasts.

    Why two buckets instead of one balance: monthly credits are use-it-or-lose-it
    and must vanish at the period end, while bonus credits are a goodwill grant that
    would be unfair to silently delete on a renewal boundary. One integer cannot
    express both lifetimes, so the sum is kept only as a convenience column.

    `credits_balance` from the previous migration is retained and now means
    monthly + bonus, backfilled below so existing balances are not lost.
    """
    # --- credit buckets on founders --------------------------------------
    op.add_column("founders", sa.Column("monthly_credits", sa.Integer(), nullable=False,
                                        server_default="0"))
    op.add_column("founders", sa.Column("bonus_credits", sa.Integer(), nullable=False,
                                        server_default="0"))
    op.add_column("founders", sa.Column("credits_expires_at",
                                        sa.DateTime(timezone=True), nullable=True))
    op.add_column("founders", sa.Column("credits_renewal_date",
                                        sa.DateTime(timezone=True), nullable=True))
    # Existing balances become bonus: they were granted with no expiry, so expiring
    # them on the first renewal would take away credits users already hold.
    op.execute("update founders set bonus_credits = credits_balance "
               "where credits_balance > 0")
    op.create_check_constraint("founders_monthly_non_negative", "founders",
                               "monthly_credits >= 0")
    op.create_check_constraint("founders_bonus_non_negative", "founders",
                               "bonus_credits >= 0")

    # --- ledger records which bucket moved -------------------------------
    op.add_column("credit_transactions",
                  sa.Column("bucket", sa.String(length=10), nullable=False,
                            server_default="bonus"))
    # Drop and recreate the type CHECK to admit the lifecycle operations.
    op.drop_constraint("credit_transactions_type_check", "credit_transactions",
                       type_="check")
    op.create_check_constraint(
        "credit_transactions_type_check", "credit_transactions",
        "type in ('add','remove','set','bonus','expire','renew','consume')")
    op.create_check_constraint(
        "credit_transactions_bucket_check", "credit_transactions",
        "bucket in ('monthly','bonus')")

    # --- feature flags ----------------------------------------------------
    op.create_table(
        "feature_flags",
        sa.Column("key", sa.String(length=60), primary_key=True),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_table(
        "feature_flag_overrides",
        sa.Column("key", sa.String(length=60),
                  sa.ForeignKey("feature_flags.key", ondelete="CASCADE"), primary_key=True),
        sa.Column("founder_id", sa.Integer(),
                  sa.ForeignKey("founders.founder_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )

    # --- broadcasts -------------------------------------------------------
    op.create_table(
        "broadcasts",
        sa.Column("broadcast_id", sa.String(length=64), primary_key=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False, server_default="info"),
        sa.Column("audience", sa.String(length=30), nullable=False, server_default="all"),
        sa.Column("audience_plan", sa.String(length=30), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.CheckConstraint("severity in ('info','warning','critical')",
                           name="broadcasts_severity_check"),
        sa.CheckConstraint("audience in ('all','plan','active','suspended')",
                           name="broadcasts_audience_check"),
    )
    op.create_index("ix_broadcasts_active", "broadcasts", ["active"])
    op.create_table(
        "broadcast_reads",
        sa.Column("broadcast_id", sa.String(length=64),
                  sa.ForeignKey("broadcasts.broadcast_id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("founder_id", sa.Integer(),
                  sa.ForeignKey("founders.founder_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("broadcast_reads")
    op.drop_index("ix_broadcasts_active", table_name="broadcasts")
    op.drop_table("broadcasts")
    op.drop_table("feature_flag_overrides")
    op.drop_table("feature_flags")
    op.drop_constraint("credit_transactions_bucket_check", "credit_transactions", type_="check")
    op.drop_constraint("credit_transactions_type_check", "credit_transactions", type_="check")
    op.create_check_constraint("credit_transactions_type_check", "credit_transactions",
                               "type in ('add','remove','set','bonus')")
    op.drop_column("credit_transactions", "bucket")
    op.drop_constraint("founders_bonus_non_negative", "founders", type_="check")
    op.drop_constraint("founders_monthly_non_negative", "founders", type_="check")
    for col in ("credits_renewal_date", "credits_expires_at", "bonus_credits", "monthly_credits"):
        op.drop_column("founders", col)
