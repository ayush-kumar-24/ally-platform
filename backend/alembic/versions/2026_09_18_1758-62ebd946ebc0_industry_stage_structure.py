"""add industry stage structure

Revision ID: 62ebd946ebc0
Revises: d3e8b41c9a52
Create Date: 2026-09-18 17:58
"""

from typing import Sequence, Union

from alembic import op


revision: str = "62ebd946ebc0"
down_revision: Union[str, Sequence[str], None] = "d3e8b41c9a52"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    bind.exec_driver_sql("""
    CREATE TABLE IF NOT EXISTS question_industry_mapping (
        id SERIAL PRIMARY KEY,
        question_id INTEGER NOT NULL REFERENCES questions(question_id),
        industry_code VARCHAR NOT NULL REFERENCES industries(industry_code),
        stage_group VARCHAR NOT NULL,
        applicability_type VARCHAR NOT NULL
            CHECK (applicability_type IN ('primary', 'supporting')),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (question_id, industry_code, stage_group)
    )
    """)

    bind.exec_driver_sql("""
    COMMENT ON TABLE question_industry_mapping IS
    'Links a question to a specific industry + stage. A question with no row here is treated as universal (applies everywhere). applicability_type: primary = this is a defining question for this industry, supporting = relevant but not core.'
    """)

    bind.exec_driver_sql("""
    CREATE TABLE IF NOT EXISTS session_context_facts (
        id SERIAL PRIMARY KEY,
        session_id VARCHAR NOT NULL,
        token VARCHAR NOT NULL,
        value VARCHAR NOT NULL,
        learned_from_answer_id INTEGER,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """)

    bind.exec_driver_sql("""
    COMMENT ON TABLE session_context_facts IS
    'Things learned about a founder DURING the current session only (e.g. they said a team question does not apply). This must never be written back into the founders table as a permanent fact -- it only affects question selection for the rest of THIS session.'
    """)

    bind.exec_driver_sql("""
    CREATE INDEX IF NOT EXISTS idx_session_context_facts_session
    ON session_context_facts(session_id)
    """)

    bind.exec_driver_sql("""
    ALTER TABLE question_tags
    ADD COLUMN IF NOT EXISTS precondition_token VARCHAR DEFAULT NULL
    """)

    bind.exec_driver_sql("""
    COMMENT ON COLUMN question_tags.precondition_token IS
    'Nullable. If set (e.g. has_team, fundraising_intent), a question with this tag should only be shown when that condition is known to be true. NULL means no precondition -- do not set this on every tag automatically, only where genuinely required.'
    """)


def downgrade() -> None:
    op.execute(
        "ALTER TABLE question_tags DROP COLUMN IF EXISTS precondition_token"
    )
    op.execute("DROP TABLE IF EXISTS session_context_facts")
    op.execute("DROP TABLE IF EXISTS question_industry_mapping")