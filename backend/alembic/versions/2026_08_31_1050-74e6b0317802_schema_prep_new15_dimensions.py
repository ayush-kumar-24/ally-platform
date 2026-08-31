"""Prepare reference data for the new 15-dimension diagnostic layer."""

from pathlib import Path
import re
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "74e6b0317802"
down_revision: Union[str, Sequence[str], None] = "63340a6e5fdb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _load_sql() -> list[str]:
    path = (
        Path(__file__).resolve().parents[2]
        / "data"
        / "question_batches"
        / "schema_prep_new15_dimensions.sql"
    )

    if not path.exists():
        raise RuntimeError(f"Schema prep SQL not found: {path}")

    sql = path.read_text(encoding="utf-8-sig")

    if "array_fill(0, ARRAY[1536])::vector" in sql:
        raise RuntimeError("Schema prep still contains zero-vector embeddings")

    # Alembic already owns the transaction.
    sql = re.sub(r"(?im)^\s*BEGIN\s*;\s*$", "", sql)
    sql = re.sub(r"(?im)^\s*COMMIT\s*;\s*$", "", sql)

    return [s.strip() for s in sql.split(";") if s.strip()]


def upgrade() -> None:
    bind = op.get_bind()

    checks = [
        ("question_tags", "tag_id", 79, 88),
        ("problems", "problem_id", 270, 275),
        ("root_causes", "root_cause_id", 1976, 2011),
    ]

    for table, column, first_id, last_id in checks:
        count = bind.execute(
            sa.text(
                f"""
                SELECT COUNT(*)
                FROM {table}
                WHERE {column} BETWEEN :first_id AND :last_id
                """
            ),
            {"first_id": first_id, "last_id": last_id},
        ).scalar()

        if count:
            raise RuntimeError(
                f"Collision detected in {table}: "
                f"{first_id}-{last_id} already contains {count} row(s)"
            )

    for statement in _load_sql():
        bind.exec_driver_sql(statement)

    expected = [
        ("question_tags", "tag_id", 79, 88, 10),
        ("problems", "problem_id", 270, 275, 6),
        ("root_causes", "root_cause_id", 1976, 2011, 36),
    ]

    for table, column, first_id, last_id, expected_count in expected:
        count = bind.execute(
            sa.text(
                f"""
                SELECT COUNT(*)
                FROM {table}
                WHERE {column} BETWEEN :first_id AND :last_id
                """
            ),
            {"first_id": first_id, "last_id": last_id},
        ).scalar()

        if count != expected_count:
            raise RuntimeError(
                f"{table}: expected {expected_count}, found {count}"
            )


def downgrade() -> None:
    bind = op.get_bind()

    bind.execute(
        sa.text(
            "DELETE FROM root_causes "
            "WHERE root_cause_id BETWEEN 1976 AND 2011"
        )
    )
    bind.execute(
        sa.text(
            "DELETE FROM problems "
            "WHERE problem_id BETWEEN 270 AND 275"
        )
    )
    bind.execute(
        sa.text(
            "DELETE FROM question_tags "
            "WHERE tag_id BETWEEN 79 AND 88"
        )
    )

    bind.exec_driver_sql(
        "SELECT setval('root_causes_root_cause_id_seq', "
        "(SELECT MAX(root_cause_id) FROM root_causes))"
    )
    bind.exec_driver_sql(
        "SELECT setval('problems_problem_id_seq', "
        "(SELECT MAX(problem_id) FROM problems))"
    )
    bind.exec_driver_sql(
        "SELECT setval('question_tags_tag_id_seq', "
        "(SELECT MAX(tag_id) FROM question_tags))"
    )
