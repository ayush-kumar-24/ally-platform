"""Seed Stage 0 Business DNA questions 2130-2229.

Revision ID: 63340a6e5fdb
Revises: c6a4e83f19d7
"""

from pathlib import Path
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "63340a6e5fdb"
down_revision: Union[str, Sequence[str], None] = "c6a4e83f19d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FIRST_ID = 2130
LAST_ID = 2229
EXPECTED_PREVIOUS_MAX = 2129
EXPECTED_COUNT = 100


def _load_batch_sql() -> list[str]:
    path = (
        Path(__file__).resolve().parents[2]
        / "data"
        / "question_batches"
        / "questions_2130_2229.sql"
    )

    if not path.exists():
        raise RuntimeError(f"Question batch file not found: {path}")

    sql = path.read_text(encoding="utf-8-sig")

    if "array_fill(0, ARRAY[1536])::vector" in sql:
        raise RuntimeError("Batch still contains zero-vector embeddings")

    return [statement.strip() for statement in sql.split(";") if statement.strip()]


def upgrade() -> None:
    bind = op.get_bind()

    # Production already uses vector(1536), but these metadata columns
    # were never added to the three embedded diagnostic tables.
    # Add them non-destructively before seed SQL references them.
    for table in ("questions", "problems", "root_causes"):
        bind.exec_driver_sql(
            f"ALTER TABLE {table} "
            "ADD COLUMN IF NOT EXISTS embedding_model varchar"
        )
        bind.exec_driver_sql(
            f"ALTER TABLE {table} "
            "ADD COLUMN IF NOT EXISTS embedding_version varchar"
        )
        bind.exec_driver_sql(
            f"ALTER TABLE {table} "
            "ADD COLUMN IF NOT EXISTS embedding_dimension integer"
        )

    max_id = bind.execute(
        sa.text("SELECT MAX(question_id) FROM questions")
    ).scalar()

    if max_id != EXPECTED_PREVIOUS_MAX:
        raise RuntimeError(
            f"Expected MAX(question_id)={EXPECTED_PREVIOUS_MAX}, found {max_id}"
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
            f"Question ID collision detected in {FIRST_ID}-{LAST_ID}"
        )

    for statement in _load_batch_sql():
        bind.exec_driver_sql(statement)

    inserted = bind.execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM questions
            WHERE question_id BETWEEN :first_id AND :last_id
            """
        ),
        {"first_id": FIRST_ID, "last_id": LAST_ID},
    ).scalar()

    if inserted != EXPECTED_COUNT:
        raise RuntimeError(
            f"Expected {EXPECTED_COUNT} questions, found {inserted}"
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
