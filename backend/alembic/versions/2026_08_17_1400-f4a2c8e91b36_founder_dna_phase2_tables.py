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
from sqlalchemy import inspect
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
    # Guarded per-object, because the migration chain above this one was
    # blocked for a day (the ally_app role issue) while the Founder DNA
    # feature needed testing. The DDL was therefore applied out-of-band from
    # scripts/founder_dna_phase2.sql -- an IF NOT EXISTS copy of exactly what
    # is below -- so on the production database these objects already exist
    # and a bare create_table here would abort the whole upgrade on
    # DuplicateTable. Same idempotency principle as 6d05993bb818 and
    # 905bddfc6aff on this same chain: an already-adopted object needs this
    # migration to no-op, not to re-create.
    bind = op.get_bind()
    insp = inspect(bind)
    existing_tables = set(insp.get_table_names())

    if 'founder_dna_questions' in existing_tables:
        print(f"NOTE [{revision}]: founder_dna_questions already exists "
              "(applied out-of-band) -- skipping its creation.")
    else:
        _create_questions_table()

    if 'founder_dna_answers' in existing_tables:
        print(f"NOTE [{revision}]: founder_dna_answers already exists "
              "(applied out-of-band) -- skipping its creation.")
    else:
        _create_answers_table()

    founders_columns = {c['name'] for c in insp.get_columns('founders')}
    if 'founder_dna_completed_at' not in founders_columns:
        op.add_column(
            'founders',
            sa.Column('founder_dna_completed_at', sa.DateTime(timezone=True), nullable=True),
        )
    if 'founder_dna_resolved_dimensions' not in founders_columns:
        op.add_column(
            'founders',
            sa.Column(
                'founder_dna_resolved_dimensions', postgresql.JSONB(astext_type=sa.Text()),
                nullable=False, server_default='[]',
            ),
        )


def _create_questions_table() -> None:
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


def _create_answers_table() -> None:
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

# NOTE on founders.founder_dna_resolved_dimensions (added in upgrade() above):
# a progress marker, NOT a scoring table -- deliberately not a
# `founder_dimension_profile`-style rubric table (that pattern was dropped
# 2026-07-27; see this migration's docstring). The LLM resolution-advisor's
# judgment stays fully prompt-driven and recomputed fresh each call; this
# JSONB array only persists WHICH dimensions it already resolved, so the
# engine need not re-ask about a settled one on every request -- the same role
# `sessions.routing_state` plays for the existing diagnosis flow.


def downgrade() -> None:
    op.drop_column('founders', 'founder_dna_resolved_dimensions')
    op.drop_column('founders', 'founder_dna_completed_at')
    op.drop_index('uq_founder_dna_answers_founder_question', table_name='founder_dna_answers')
    op.drop_index('idx_founder_dna_answers_founder', table_name='founder_dna_answers')
    op.drop_table('founder_dna_answers')
    op.drop_index('idx_founder_dna_questions_dimension_stage', table_name='founder_dna_questions')
    op.drop_table('founder_dna_questions')
