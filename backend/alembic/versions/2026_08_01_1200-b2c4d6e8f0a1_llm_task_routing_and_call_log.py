"""llm task->model routing table + per-call telemetry log

Seeds every LLM task to Claude Sonnet for now (one model, one provider). Which
model serves which task is DATA here, changed with an UPDATE -- not a deploy.

Revision ID: b2c4d6e8f0a1
Revises: f1a2d3c4b5e6
Create Date: 2026-08-01 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b2c4d6e8f0a1"
down_revision: Union[str, Sequence[str], None] = "f1a2d3c4b5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TASKS = [
    "answer_interpretation",
    "next_question_selection",
    "distress_detection",
    "diagnosis_reasoning",
    "answer_consistency",
    "archetype_assignment",
    "report_narrative",
]


def upgrade() -> None:
    op.create_table(
        "model_task_routing",
        sa.Column("task", sa.String(length=50), primary_key=True),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("model_id", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_table(
        "llm_call_log",
        sa.Column("call_id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("task", sa.String(length=50), nullable=False),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("model_id", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("output_tokens", sa.Integer()),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("estimated_cost_usd", sa.Numeric(12, 6)),
        sa.Column("founder_id", sa.Integer()),
        sa.Column("session_id", sa.Integer()),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_llm_call_log_task", "llm_call_log", ["task"])
    op.create_index("ix_llm_call_log_created_at", "llm_call_log", ["created_at"])
    op.create_index("ix_llm_call_log_founder_id", "llm_call_log", ["founder_id"])
    op.create_index("ix_llm_call_log_session_id", "llm_call_log", ["session_id"])

    routing = sa.table(
        "model_task_routing",
        sa.column("task", sa.String),
        sa.column("provider", sa.String),
        sa.column("model_id", sa.String),
        sa.column("notes", sa.Text),
    )
    op.bulk_insert(
        routing,
        [
            {"task": t, "provider": "anthropic", "model_id": "claude-sonnet-5",
             "notes": "seed: one model for all tasks while validating"}
            for t in _TASKS
        ],
    )


def downgrade() -> None:
    op.drop_table("llm_call_log")
    op.drop_table("model_task_routing")
