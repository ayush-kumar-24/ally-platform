from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from sqlalchemy import create_engine, text

from app.core.config import settings
from app.services import embeddings


FIRST_ID = 2130
LAST_ID = 2229
EXPECTED_QUESTIONS = 100
EXPECTED_DIMENSION = 1536
EXPECTED_MODEL = "text-embedding-3-small"
EXPECTED_VERSION = "openai-3-small-v1"


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{float(v):.8g}" for v in vector) + "]"


def main() -> int:
    if settings.EMBEDDING_MODEL != EXPECTED_MODEL:
        print(
            f"EMBEDDING_MODEL mismatch: "
            f"{settings.EMBEDDING_MODEL} != {EXPECTED_MODEL}",
            file=sys.stderr,
        )
        return 2

    if settings.EMBEDDING_DIMENSION != EXPECTED_DIMENSION:
        print(
            f"EMBEDDING_DIMENSION mismatch: "
            f"{settings.EMBEDDING_DIMENSION} != {EXPECTED_DIMENSION}",
            file=sys.stderr,
        )
        return 2

    if settings.EMBEDDING_VERSION != EXPECTED_VERSION:
        print(
            f"EMBEDDING_VERSION mismatch: "
            f"{settings.EMBEDDING_VERSION} != {EXPECTED_VERSION}",
            file=sys.stderr,
        )
        return 2

    provider = embeddings.get_provider("openai")

    if provider.dimension != EXPECTED_DIMENSION:
        print(
            f"Provider dimension {provider.dimension} "
            f"!= expected {EXPECTED_DIMENSION}",
            file=sys.stderr,
        )
        return 2

    engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

    with engine.connect() as conn:
        batch = conn.execute(
            text(
                """
                SELECT
                    COUNT(*) AS total,
                    MIN(question_id) AS min_id,
                    MAX(question_id) AS max_id
                FROM questions
                WHERE question_id BETWEEN :first_id AND :last_id
                """
            ),
            {"first_id": FIRST_ID, "last_id": LAST_ID},
        ).mappings().one()

        rows = conn.execute(
            text(
                """
                SELECT question_id, COALESCE(question_text, '') AS content
                FROM questions
                WHERE question_id BETWEEN :first_id AND :last_id
                  AND embedding IS NULL
                ORDER BY question_id
                """
            ),
            {"first_id": FIRST_ID, "last_id": LAST_ID},
        ).mappings().all()

    if (
        batch["total"] != EXPECTED_QUESTIONS
        or batch["min_id"] != FIRST_ID
        or batch["max_id"] != LAST_ID
    ):
        print(
            "Batch guard failed: "
            f"expected {EXPECTED_QUESTIONS} questions "
            f"with IDs {FIRST_ID}-{LAST_ID}; "
            f"found total={batch['total']}, "
            f"range={batch['min_id']}-{batch['max_id']}",
            file=sys.stderr,
        )
        return 1

    pending = len(rows)

    print(f"Batch: {FIRST_ID}-{LAST_ID}")
    print(f"Questions present: {batch['total']}/{EXPECTED_QUESTIONS}")
    print(f"NULL embeddings to process: {pending}")
    print(
        f"Provider: {provider.name}/{provider.model} "
        f"({provider.dimension}-d)"
    )

    if pending == 0:
        print("Nothing to do. Batch already embedded.")
        return 0

    done = 0

    for row in rows:
        vector = provider.embed(row["content"] or "")

        if len(vector) != EXPECTED_DIMENSION:
            print(
                f"Question {row['question_id']}: "
                f"provider returned {len(vector)} dimensions, "
                f"expected {EXPECTED_DIMENSION}",
                file=sys.stderr,
            )
            return 1

        # Commit one question at a time so the script is safely resumable.
        with engine.begin() as conn:
            result = conn.execute(
                text(
                    """
                    UPDATE questions
                    SET embedding = CAST(:vec AS vector),
                        embedding_model = :model,
                        embedding_dimension = :dimension,
                        embedding_version = :version
                    WHERE question_id = :question_id
                      AND question_id BETWEEN :first_id AND :last_id
                      AND embedding IS NULL
                    """
                ),
                {
                    "vec": _vector_literal(vector),
                    "model": EXPECTED_MODEL,
                    "dimension": EXPECTED_DIMENSION,
                    "version": EXPECTED_VERSION,
                    "question_id": row["question_id"],
                    "first_id": FIRST_ID,
                    "last_id": LAST_ID,
                },
            )

        if result.rowcount != 1:
            print(
                f"Question {row['question_id']}: expected exactly "
                f"1 updated row, got {result.rowcount}",
                file=sys.stderr,
            )
            return 1

        done += 1

        if done % 10 == 0 or done == pending:
            print(f"Embedded: {done}/{pending}")

    print(f"\nEmbedding backfill complete: {done}/{pending}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
