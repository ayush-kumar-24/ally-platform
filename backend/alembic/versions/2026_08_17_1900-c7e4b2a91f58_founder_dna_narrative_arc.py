"""founder DNA: narrative arc, wow close, forced-choice format

Brings the phase-2 question bank in line with
`GoXL_Founder_DNA_Decoding_Journey.docx`, which the first cut only partly
followed. Three of the doc's Section-3 journey principles needed schema to
express at all:

  * "Narrative arc -- the journey opens wide and emotional (identity, origin)
    before narrowing into structured territory (decision style, values)."
    -> `arc_position`, the question's slot in the doc's own per-stage table.
    The engine orders by this instead of the round-robin it used before, so a
    founder walks the sequence the doc designed rather than an arbitrary one.

  * "The 'wow' close -- every stage-specific journey ends on one deliberately
    bigger, more reflective question."
    -> `is_closing`. A flag rather than just "highest arc_position" because
    the engine must GUARANTEE it runs last even when adaptive skipping cuts
    the middle of the journey short; position alone would let it be skipped.

  * "Mixed formats -- every dimension has at least one non-text format."
    -> `forced_choice` added to the format CHECK, plus `options` to hold its
    choices. Four of the doc's questions are Forced Choice; the first cut
    stored two of them as `narrative`, so a founder typed prose where the doc
    intends a pick-one. (The six two-image Visual questions stay deferred --
    text-only was a deliberate v1 scope decision.)

Revision ID: c7e4b2a91f58
Revises: f4a2c8e91b36
Create Date: 2026-08-17 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision: str = 'c7e4b2a91f58'
down_revision: Union[str, Sequence[str], None] = 'f4a2c8e91b36'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = 'founder_dna_questions'
_OLD_FORMATS = ('narrative', 'scenario')
_NEW_FORMATS = ('narrative', 'scenario', 'forced_choice')


def upgrade() -> None:
    cols = {c['name'] for c in inspect(op.get_bind()).get_columns(_TABLE)}

    if 'arc_position' not in cols:
        # Slot in the doc's per-stage table. Defaults to 0 so any row seeded
        # before this migration sorts first rather than vanishing from the
        # ordering; the reseed assigns real positions.
        op.add_column(_TABLE, sa.Column(
            'arc_position', sa.Integer(), nullable=False, server_default='0'))

    if 'is_closing' not in cols:
        op.add_column(_TABLE, sa.Column(
            'is_closing', sa.Boolean(), nullable=False, server_default=sa.false()))

    if 'options' not in cols:
        # Choice labels for `forced_choice`; NULL for the text formats.
        op.add_column(_TABLE, sa.Column(
            'options', postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    # Widen the format CHECK to admit forced_choice.
    op.drop_constraint('founder_dna_questions_format_check', _TABLE, type_='check')
    op.create_check_constraint(
        'founder_dna_questions_format_check', _TABLE,
        "format = ANY (ARRAY[" + ",".join(f"'{f}'" for f in _NEW_FORMATS) + "]::text[])",
    )

    # At most one closing question per stage -- the doc's "wow close" is
    # singular by design ("ends on ONE deliberately bigger question"), and the
    # engine reserves exactly one slot for it. A second would silently never
    # be asked.
    op.create_index(
        'uq_founder_dna_one_closing_per_stage', _TABLE, ['stage_group'],
        unique=True, postgresql_where=sa.text('is_closing'),
    )


def downgrade() -> None:
    op.drop_index('uq_founder_dna_one_closing_per_stage', table_name=_TABLE)

    # Anything using the widened format must go before the CHECK narrows, or
    # the constraint cannot be re-created.
    op.execute(
        f"DELETE FROM {_TABLE} WHERE format NOT IN "
        "(" + ",".join(f"'{f}'" for f in _OLD_FORMATS) + ")"
    )
    op.drop_constraint('founder_dna_questions_format_check', _TABLE, type_='check')
    op.create_check_constraint(
        'founder_dna_questions_format_check', _TABLE,
        "format = ANY (ARRAY[" + ",".join(f"'{f}'" for f in _OLD_FORMATS) + "]::text[])",
    )

    op.drop_column(_TABLE, 'options')
    op.drop_column(_TABLE, 'is_closing')
    op.drop_column(_TABLE, 'arc_position')
