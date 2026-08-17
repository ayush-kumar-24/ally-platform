"""founder DNA phase-2: question bank + answers + completion marker

Adds the storage for the adaptive Founder DNA question phase (text-only v1 --
narrative/scenario questions across 6 dimensions the report pipeline already
names as absent: purpose_mission, core_values, mindset_excellence,
energy_patterns, decision_style, focus_attention -- see
app/api/v1/reasoning/engines/founder_dna_extras.py's docstring).

Deliberately NOT a `founder_dimensions` catalogue table -- that table (and its
paired `founder_dimension_profile`) existed once and was dropped 2026-07-27
in favour of prompt-driven scoring with no table
(docs/frontend_integration_mapping.md). This migration follows that same
precedent: the 6 dimension codes live as a Python StrEnum
(app/models/enums.py::FounderDnaDimension), not a DB row, matching how
CATEGORY_SEQUENCE in the existing diagnosis engine is a Python constant too.

`founder_dna_questions` is a new, purpose-built table rather than reusing
`questions` -- `questions` is tightly coupled to the business root-cause
diagnosis engine (root_cause_id, problem_id, red/green flag patterns); these
identity questions have no root cause to resolve against.

`founder_dna_answers` mirrors `founder_visual_choices`'s shape (founder_id +
question FK + answer + timestamp) rather than the `answers` table, which
carries scoring/confirmation-status columns specific to root-cause diagnosis
that don't apply here.

`founders.founder_dna_completed_at` gates entry to the existing diagnosis
flow -- the agreed sequencing is Founder DNA fully first, then Business DNA.

Revision ID: f4a2c8e91b36
Revises: b3d7f19a4c62
Create Date: 2026-08-17 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'f4a2c8e91b36'
down_revision: Union[str, Sequence[str], None] = 'b3d7f19a4c62'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DIMENSION_CODES = (
    'purpose_mission', 'core_values', 'mindset_excellence',
    'energy_patterns', 'decision_style', 'focus_attention',
)
_STAGE_GROUPS = ('Stage 0', 'Stage 0→1', 'Stage 1→10+')
_FORMATS = ('narrative', 'scenario')


def upgrade() -> None:
    op.create_table(
        'founder_dna_questions',
        sa.Column('founder_dna_question_id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('dimension_code', sa.String(30), nullable=False),
        sa.Column('stage_group', sa.String(20), nullable=False),
        sa.Column('format', sa.String(20), nullable=False, server_default='narrative'),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint(
            "dimension_code = ANY (ARRAY[" + ",".join(f"'{c}'" for c in _DIMENSION_CODES) + "]::text[])",
            name='founder_dna_questions_dimension_code_check',
        ),
        sa.CheckConstraint(
            "stage_group = ANY (ARRAY[" + ",".join(f"'{g}'" for g in _STAGE_GROUPS) + "]::text[])",
            name='founder_dna_questions_stage_group_check',
        ),
        sa.CheckConstraint(
            "format = ANY (ARRAY[" + ",".join(f"'{f}'" for f in _FORMATS) + "]::text[])",
            name='founder_dna_questions_format_check',
        ),
    )
    op.create_index(
        'idx_founder_dna_questions_dimension_stage',
        'founder_dna_questions', ['dimension_code', 'stage_group'],
    )

    op.create_table(
        'founder_dna_answers',
        sa.Column('founder_dna_answer_id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('founder_id', sa.Integer(), nullable=False),
        sa.Column('founder_dna_question_id', sa.Integer(), nullable=False),
        sa.Column('answer_text', sa.Text(), nullable=False),
        sa.Column('answered_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['founder_id'], ['founders.founder_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['founder_dna_question_id'], ['founder_dna_questions.founder_dna_question_id']
        ),
    )
    op.create_index('idx_founder_dna_answers_founder', 'founder_dna_answers', ['founder_id'])
    op.create_index(
        'uq_founder_dna_answers_founder_question',
        'founder_dna_answers', ['founder_id', 'founder_dna_question_id'],
        unique=True,
    )

    op.add_column(
        'founders',
        sa.Column('founder_dna_completed_at', sa.DateTime(timezone=True), nullable=True),
    )
    # Progress marker, not a scoring table -- deliberately NOT a
    # `founder_dimension_profile`-style rubric table (that pattern was
    # dropped 2026-07-27; see this migration's docstring). The LLM
    # resolution-advisor's judgment is still fully prompt-driven and
    # recomputed fresh each call; this JSONB array just needs to persist
    # *which* dimensions it already resolved so the engine doesn't have to
    # re-ask about a settled dimension on every subsequent request -- the
    # same role `sessions.routing_state` plays for the existing diagnosis
    # flow's confidence decision.
    op.add_column(
        'founders',
        sa.Column(
            'founder_dna_resolved_dimensions', postgresql.JSONB(astext_type=sa.Text()),
            nullable=False, server_default='[]',
        ),
    )


def downgrade() -> None:
    op.drop_column('founders', 'founder_dna_resolved_dimensions')
    op.drop_column('founders', 'founder_dna_completed_at')
    op.drop_index('uq_founder_dna_answers_founder_question', table_name='founder_dna_answers')
    op.drop_index('idx_founder_dna_answers_founder', table_name='founder_dna_answers')
    op.drop_table('founder_dna_answers')
    op.drop_index('idx_founder_dna_questions_dimension_stage', table_name='founder_dna_questions')
    op.drop_table('founder_dna_questions')
