"""Risk Appetite -- the fifteenth Founder DNA dimension.

Adds `risk_appetite` to the `founder_dna_questions_dimension_code_check`
constraint and seeds its six questions (two per stage group).

WHY A MIGRATION AND NOT RAW SQL
-------------------------------
This content is already live on Supabase, and the tempting move was to run the
same INSERT straight onto RDS. It is not safe to: the CHECK constraint has to be
widened first or every row is rejected, the IDs have to be verified free because
the two databases do not share an ID space, and the accompanying code change
(FounderDnaDimension gaining RISK_APPETITE, MAX_FOUNDER_DNA_QUESTIONS 17 -> 18)
has to ship in the same deploy. Split those apart and you get a window where the
enum knows a dimension the database rejects, or a database holding questions the
budget has no room to ask.

WHAT SHIPS WITH THIS
--------------------
  * app/models/enums.py            -- FounderDnaDimension.RISK_APPETITE
  * app/core/config.py             -- MAX_FOUNDER_DNA_QUESTIONS 17 -> 18
                                      (15 base + 2 follow-ups + 1 close)
  * scripts/seed_founder_dna_questions.py -- the same six questions, so a
                                      fresh environment seeded from the script
                                      matches one migrated from here

EMBEDDINGS
----------
The seeded rows carry NO embedding -- NULL, not a zero-vector placeholder.
`founder_dna_questions.embedding` is nullable, so nothing forces a placeholder,
and a placeholder would be actively harmful: `array_fill(0, ARRAY[1536])` is not
NULL, so the backfill's selector skips it and the question stays permanently
invisible to similarity search while looking embedded. That is exactly what
happened to 1,213 questions seeded earlier. This file is asserted free of that
pattern below, the same guard 74e6b0317802 applies.

Run `scripts/embedding_migration/02_regenerate_embeddings.py` after deploying to
fill them.

Revision ID: a3f81c05e6d7
Revises: d5b81e37c9a2
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a3f81c05e6d7"
down_revision: Union[str, Sequence[str], None] = "d5b81e37c9a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TABLE = "founder_dna_questions"
_CONSTRAINT = "founder_dna_questions_dimension_code_check"
_NEW_DIMENSION = "risk_appetite"
_FIRST_ID, _LAST_ID = 159, 164

#: The SQL file holds exactly two executable statements: the INSERT and the
#: sequence setval. Asserted rather than assumed -- see _load_sql.
_EXPECTED_STATEMENTS = 2

#: The fourteen that existed before this migration, in the enum's own order,
#: plus the new one. Spelled out rather than read from the enum: a migration
#: must describe the database at ITS point in history, and an enum that gains a
#: sixteenth dimension later must not silently change what this one did.
_DIMENSIONS = (
    "archetype", "core_motivation", "origin", "purpose_mission", "vision",
    "core_values", "mindset_excellence", "strengths_blind_spots",
    "energy_patterns", "stress_response", "decision_style",
    "communication_preference", "focus_attention", "emotional_intelligence",
    _NEW_DIMENSION,
)


def _sql_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "data" / "question_batches" / "risk_appetite_dimension.sql"
    )


def _load_sql() -> list[str]:
    path = _sql_path()
    if not path.exists():
        raise RuntimeError(f"Risk Appetite SQL not found: {path}")

    sql = path.read_text(encoding="utf-8-sig")

    # Same guard 74e6b0317802 uses. A zero vector satisfies a NOT NULL column
    # and then hides from the embedding backfill, so it is worse than no row.
    if "array_fill(0, ARRAY[1536])::vector" in sql:
        raise RuntimeError("Risk Appetite SQL still contains zero-vector embeddings")

    # Alembic already owns the transaction.
    sql = re.sub(r"(?im)^\s*BEGIN\s*;\s*$", "", sql)
    sql = re.sub(r"(?im)^\s*COMMIT\s*;\s*$", "", sql)

    # Strip full-line SQL comments BEFORE splitting on ";".
    #
    # Splitting a file on ";" treats a semicolon inside a comment as a
    # statement boundary. This file's own prose contained one -- "...warns
    # against; asking which feeling actually shows up..." -- which cut the
    # header comment in two and handed Postgres a fragment beginning "asking
    # which feeling actually shows up, or". It failed the production migration
    # with `syntax error at or near "asking"`.
    #
    # Fixing the punctuation in that one sentence would have unblocked the
    # deploy and left the trap armed for the next person who writes a
    # semicolon in a comment. Removing the comments is the fix; the count
    # assertion below is what makes a future recurrence fail here, loudly and
    # locally, instead of on a production migration task.
    sql = re.sub(r"(?m)^\s*--.*$", "", sql)

    statements = [s.strip() for s in sql.split(";") if s.strip()]

    if len(statements) != _EXPECTED_STATEMENTS:
        raise RuntimeError(
            f"Expected exactly {_EXPECTED_STATEMENTS} Risk Appetite SQL "
            f"statements, found {len(statements)}. The file is malformed, or a "
            "semicolon appears somewhere the splitter treats as a boundary."
        )

    return statements


def _dimension_check(dimensions: Sequence[str]) -> str:
    allowed = ", ".join(f"'{d}'::text" for d in dimensions)
    return f"(dimension_code)::text = ANY (ARRAY[{allowed}])"


def upgrade() -> None:
    bind = op.get_bind()

    # 1. IDs must be free. Supabase and RDS do not share an ID space, so the
    #    fact that 159-164 are correct THERE says nothing about here. Failing
    #    loudly beats overwriting six unrelated questions.
    taken = bind.execute(
        sa.text(
            f"SELECT COUNT(*) FROM {_TABLE} "
            "WHERE founder_dna_question_id BETWEEN :first AND :last"
        ),
        {"first": _FIRST_ID, "last": _LAST_ID},
    ).scalar()
    if taken:
        raise RuntimeError(
            f"{_TABLE} ids {_FIRST_ID}-{_LAST_ID} are not free ({taken} row(s) "
            "present). Risk Appetite cannot be seeded at these ids -- resolve "
            "the collision before re-running."
        )

    # 2. Widen the constraint BEFORE inserting, or every row is rejected.
    op.execute(f'ALTER TABLE public."{_TABLE}" DROP CONSTRAINT IF EXISTS "{_CONSTRAINT}"')
    op.execute(
        f'ALTER TABLE public."{_TABLE}" ADD CONSTRAINT "{_CONSTRAINT}" '
        f"CHECK ({_dimension_check(_DIMENSIONS)})"
    )

    # 3. Seed the questions.
    for statement in _load_sql():
        op.execute(sa.text(statement))

    # 4. Assert what we actually got. A seed that silently inserts four of six
    #    rows is a phase that can never resolve the dimension for one stage
    #    group, and nothing downstream would report it.
    seeded = bind.execute(
        sa.text(
            f"SELECT COUNT(*) FROM {_TABLE} WHERE dimension_code = :dim AND is_active"
        ),
        {"dim": _NEW_DIMENSION},
    ).scalar()
    if seeded != 6:
        raise RuntimeError(
            f"Expected 6 active {_NEW_DIMENSION} questions after seeding, found {seeded}."
        )

    groups = bind.execute(
        sa.text(
            f"SELECT COUNT(DISTINCT stage_group) FROM {_TABLE} "
            "WHERE dimension_code = :dim AND is_active"
        ),
        {"dim": _NEW_DIMENSION},
    ).scalar()
    if groups != 3:
        raise RuntimeError(
            f"{_NEW_DIMENSION} must cover all 3 stage groups, found {groups}. "
            "A founder in an uncovered group could never resolve this dimension."
        )


def downgrade() -> None:
    # Answers first: the questions cannot go while rows reference them, and a
    # founder's answer to a dimension we are removing has nothing to say.
    op.execute(
        f"DELETE FROM founder_dna_answers WHERE founder_dna_question_id IN "
        f"(SELECT founder_dna_question_id FROM {_TABLE} "
        f"WHERE dimension_code = '{_NEW_DIMENSION}')"
    )
    op.execute(f"DELETE FROM {_TABLE} WHERE dimension_code = '{_NEW_DIMENSION}'")

    # Narrow the constraint back. Done AFTER the delete, or the surviving rows
    # would violate the constraint being added.
    op.execute(f'ALTER TABLE public."{_TABLE}" DROP CONSTRAINT IF EXISTS "{_CONSTRAINT}"')
    op.execute(
        f'ALTER TABLE public."{_TABLE}" ADD CONSTRAINT "{_CONSTRAINT}" '
        f"CHECK ({_dimension_check([d for d in _DIMENSIONS if d != _NEW_DIMENSION])})"
    )
