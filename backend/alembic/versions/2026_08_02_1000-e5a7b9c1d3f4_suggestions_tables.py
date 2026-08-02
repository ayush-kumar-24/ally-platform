"""new tables: suggestions + suggestion_feedback -- fixes the same in-memory bug

SuggestionService's InMemorySuggestionRepository is a process-level singleton:
every AI-generated suggestion and every founder's accept/dismiss feedback on it
is lost on restart/redeploy and cannot be shared across worker processes.

No prior table existed for suggestions (unlike conversations/file_uploads, which
already existed and only needed extra columns), so both tables are new. Both use
the domain's own string ids as their primary key directly -- no external_id
indirection is needed since there is no legacy integer-PK table to reconcile with.
conversation_id / suggestion_id reference conversations.external_id /
suggestions.suggestion_id, both already unique.

Revision ID: e5a7b9c1d3f4
Revises: d4f6a8c0e2b3
Create Date: 2026-08-02 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "e5a7b9c1d3f4"
down_revision: Union[str, Sequence[str], None] = "d4f6a8c0e2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SUGGESTION_TYPES = (
    "follow_up", "clarification", "missing_information", "summarization",
    "attachment_review", "link_discussion", "continue_conversation", "goal_reminder",
)
_PRIORITIES = ("low", "medium", "high", "critical")
_SOURCES = ("conversation", "ai_response", "attachment", "link", "context", "system")
_STATUSES = ("active", "archived", "deleted")
_FEEDBACK_TYPES = ("pending", "accepted", "dismissed", "ignored")


def _in_list(values: tuple[str, ...]) -> str:
    return "(" + ",".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    op.create_table(
        "suggestions",
        sa.Column("suggestion_id", sa.String(length=64), primary_key=True),
        sa.Column(
            "conversation_id", sa.String(length=64),
            sa.ForeignKey("conversations.external_id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "founder_id", sa.Integer(),
            sa.ForeignKey("founders.founder_id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("suggestion_type", sa.String(length=30), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("priority", sa.String(length=10), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("reason_code", sa.String(length=50), nullable=False),
        sa.Column("reason_description", sa.Text(), nullable=False),
        sa.Column("dedup_key", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'active'")),
        sa.Column("feedback", sa.String(length=20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("relevance_score", sa.Numeric(6, 4), nullable=False, server_default=sa.text("0")),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("meta_data", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.CheckConstraint(f"suggestion_type IN {_in_list(_SUGGESTION_TYPES)}", name="suggestions_type_check"),
        sa.CheckConstraint(f"priority IN {_in_list(_PRIORITIES)}", name="suggestions_priority_check"),
        sa.CheckConstraint(f"source IN {_in_list(_SOURCES)}", name="suggestions_source_check"),
        sa.CheckConstraint(f"status IN {_in_list(_STATUSES)}", name="suggestions_status_check"),
        sa.CheckConstraint(f"feedback IN {_in_list(_FEEDBACK_TYPES)}", name="suggestions_feedback_check"),
    )
    op.create_index("ix_suggestions_conversation_id", "suggestions", ["conversation_id"])
    op.create_index("ix_suggestions_founder_id", "suggestions", ["founder_id"])

    op.create_table(
        "suggestion_feedback",
        sa.Column("feedback_id", sa.String(length=64), primary_key=True),
        sa.Column(
            "suggestion_id", sa.String(length=64),
            sa.ForeignKey("suggestions.suggestion_id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "founder_id", sa.Integer(),
            sa.ForeignKey("founders.founder_id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("feedback_type", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("note", sa.Text(), nullable=True),
        sa.CheckConstraint(f"feedback_type IN {_in_list(_FEEDBACK_TYPES)}", name="suggestion_feedback_type_check"),
    )
    op.create_index("ix_suggestion_feedback_suggestion_id", "suggestion_feedback", ["suggestion_id"])


def downgrade() -> None:
    op.drop_table("suggestion_feedback")
    op.drop_table("suggestions")
