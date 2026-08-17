"""founder DNA: widen to all 13 doc dimensions + EQ

Product decision (2026-08-18): every dimension the dashboard renders is ASKED
in the Founder DNA phase, rather than some being asked and others derived.
Fourteen in total -- the doc's thirteen plus an Emotional Intelligence
dimension GoXL added on top of it.

Why this is a net improvement, not just more questions: three of the
dashboard's cards (strengths_blind_spots, stress_response,
communication_preference) were previously filled by matching a founder's
detected root causes against the blind_spots / behaviour_patterns
catalogues. Verified live -- that catalogue carries no entries linked to
psychology-range root-cause codes, which is what most founders actually
score, so those three cards rendered EMPTY on real reports. Asking directly
turns three unreliable cards into three guaranteed ones.

Two of the new codes (origin, vision) also exist as onboarding free text on
the founders row. The asked answer wins where both are present -- see the
update order in ReasoningService._persist -- because a considered answer to
a situational question beats a signup-form field.

`archetype` is asked via the doc's own "Identity" questions ("Who were you as
a leader in year one, and who are you now?") rather than a self-label pick:
the archetype engine infers Operator / Problem Solver / etc. from a founder's
own language, and asking someone to choose their own archetype would both
contradict the doc's working principle (self-rating is the thing it warns
against) and hand the engine a label instead of the language it reads.

Revision ID: d8b3f6c204ae
Revises: c7e4b2a91f58
Create Date: 2026-08-18 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = 'd8b3f6c204ae'
down_revision: Union[str, Sequence[str], None] = 'c7e4b2a91f58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = 'founder_dna_questions'
_CONSTRAINT = 'founder_dna_questions_dimension_code_check'

_OLD_CODES = (
    'purpose_mission', 'core_values', 'mindset_excellence',
    'energy_patterns', 'decision_style', 'focus_attention',
)

_NEW_CODES = _OLD_CODES + (
    'archetype',                 # doc dim 1  -- asked via Identity questions
    'core_motivation',           # doc dim 2
    'origin',                    # doc dim 3  -- also onboarding free text
    'vision',                    # doc dim 5  -- also onboarding free text
    'strengths_blind_spots',     # doc dim 8  -- was catalogue-derived (empty)
    'stress_response',           # doc dim 10 -- was catalogue-derived (empty)
    'communication_preference',  # doc dim 12 -- was catalogue-derived (empty)
    'emotional_intelligence',    # GoXL addition, not in the doc's thirteen
)


def _set_codes(codes: tuple[str, ...]) -> None:
    op.drop_constraint(_CONSTRAINT, _TABLE, type_='check')
    op.create_check_constraint(
        _CONSTRAINT, _TABLE,
        "dimension_code = ANY (ARRAY["
        + ",".join(f"'{c}'" for c in codes) + "]::text[])",
    )


def upgrade() -> None:
    _set_codes(_NEW_CODES)


def downgrade() -> None:
    # Rows on the widened codes must go before the CHECK narrows, or it
    # cannot be re-created. Answers referencing them go too (FK), so this is
    # destructive by nature -- acceptable for a question-bank downgrade,
    # which is content rather than founder-authored data.
    op.execute(
        f"DELETE FROM founder_dna_answers WHERE founder_dna_question_id IN "
        f"(SELECT founder_dna_question_id FROM {_TABLE} "
        "WHERE dimension_code NOT IN ("
        + ",".join(f"'{c}'" for c in _OLD_CODES) + "))"
    )
    op.execute(
        f"DELETE FROM {_TABLE} WHERE dimension_code NOT IN ("
        + ",".join(f"'{c}'" for c in _OLD_CODES) + ")"
    )
    _set_codes(_OLD_CODES)
