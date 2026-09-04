"""Seed diagnostic questions 2230-3342."""

from pathlib import Path
import re
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "ba7ca1acfa53"
down_revision: Union[str, Sequence[str], None] = "74e6b0317802"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FIRST_ID = 2230
LAST_ID = 3342
EXPECTED_PREVIOUS_MAX = 2229
EXPECTED_QUESTIONS = 1113
EXPECTED_MAPPINGS = 1431

FILES = [
    "questions_2230_2274.sql",
    "questions_2275_2413.sql",
    "questions_2414_2655.sql",
    "questions_2656_2755.sql",
    "questions_2756_2965.sql",
    "questions_2966_3342.sql",
]


def _load_sql() -> list[str]:
    base = (
        Path(__file__).resolve().parents[2]
        / "data"
        / "question_batches"
    )

    statements: list[str] = []

    for name in FILES:
        path = base / name

        if not path.exists():
            raise RuntimeError(f"Question batch not found: {path}")

        sql = path.read_text(encoding="utf-8-sig")

        if "array_fill(0, ARRAY[1536])::vector" in sql:
            raise RuntimeError(f"{name} still contains zero-vector embeddings")

        sql = re.sub(r"(?im)^\s*BEGIN\s*;\s*$", "", sql)
        sql = re.sub(r"(?im)^\s*COMMIT\s*;\s*$", "", sql)

        statements.extend(
            s.strip() for s in sql.split(";") if s.strip()
        )

    return statements


def upgrade() -> None:
    bind = op.get_bind()

    max_id = bind.execute(
        sa.text("SELECT MAX(question_id) FROM questions")
    ).scalar()

    if max_id != EXPECTED_PREVIOUS_MAX:
        raise RuntimeError(
            f"Expected MAX(question_id)={EXPECTED_PREVIOUS_MAX}, "
            f"found {max_id}"
        )

    collisions = bind.execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM questions
            WHERE question_id BETWEEN :first_id AND :last_id
            """
        ),
        {"first_id": FIRST_ID, "last_id": LAST_ID},
    ).scalar()

    if collisions:
        raise RuntimeError(
            f"Question ID collision in {FIRST_ID}-{LAST_ID}: "
            f"{collisions} row(s)"
        )

    for statement in _load_sql():
        bind.exec_driver_sql(statement)

    question_count = bind.execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM questions
            WHERE question_id BETWEEN :first_id AND :last_id
            """
        ),
        {"first_id": FIRST_ID, "last_id": LAST_ID},
    ).scalar()

    if question_count != EXPECTED_QUESTIONS:
        raise RuntimeError(
            f"Expected {EXPECTED_QUESTIONS} questions, "
            f"found {question_count}"
        )

    mapping_count = bind.execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM question_tag_mapping
            WHERE question_id BETWEEN :first_id AND :last_id
            """
        ),
        {"first_id": FIRST_ID, "last_id": LAST_ID},
    ).scalar()

    if mapping_count != EXPECTED_MAPPINGS:
        raise RuntimeError(
            f"Expected {EXPECTED_MAPPINGS} mappings, "
            f"found {mapping_count}"
        )

    bind.exec_driver_sql(
        "SELECT setval('questions_question_id_seq', "
        "(SELECT MAX(question_id) FROM questions))"
    )
    bind.exec_driver_sql(
        "SELECT setval('question_tag_mapping_mapping_id_seq', "
        "(SELECT MAX(mapping_id) FROM question_tag_mapping))"
    )


def downgrade() -> None:
    bind = op.get_bind()

    bind.execute(
        sa.text(
            """
            DELETE FROM question_tag_mapping
            WHERE question_id BETWEEN :first_id AND :last_id
            """
        ),
        {"first_id": FIRST_ID, "last_id": LAST_ID},
    )

    bind.execute(
        sa.text(
            """
            DELETE FROM questions
            WHERE question_id BETWEEN :first_id AND :last_id
            """
        ),
        {"first_id": FIRST_ID, "last_id": LAST_ID},
    )

    bind.exec_driver_sql(
        "SELECT setval('questions_question_id_seq', "
        "(SELECT MAX(question_id) FROM questions))"
    )
    bind.exec_driver_sql(
        "SELECT setval('question_tag_mapping_mapping_id_seq', "
        "(SELECT MAX(mapping_id) FROM question_tag_mapping))"
    )
