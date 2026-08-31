from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from sqlalchemy import create_engine, text

from app.core.config import settings
from app.services import embeddings


EXPECTED_DIMENSION = 1536
EXPECTED_MODEL = "text-embedding-3-small"
EXPECTED_VERSION = "openai-3-small-v1"

TARGETS = [
    {
        "table": "questions",
        "pk": "question_id",
        "content": "COALESCE(question_text, '')",
        "first": 2230,
        "last": 3342,
        "expected": 1113,
    },
    {
        "table": "problems",
        "pk": "problem_id",
        "content": (
            "COALESCE(problem_name, '') || ' ? ' || "
            "COALESCE(description, '')"
        ),
        "first": 270,
        "last": 275,
        "expected": 6,
    },
    {
        "table": "root_causes",
        "pk": "root_cause_id",
        "content": (
            "COALESCE(root_cause_name, '') || ' ? ' || "
            "COALESCE(explanation, '')"
        ),
        "first": 1976,
        "last": 2011,
        "expected": 36,
    },
]


def vector_literal(vector: list[float]) -> str:
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
            f"!= {EXPECTED_DIMENSION}",
            file=sys.stderr,
        )
        return 2

    if provider.model != EXPECTED_MODEL:
        print(
            f"Provider model {provider.model} "
            f"!= {EXPECTED_MODEL}",
            file=sys.stderr,
        )
        return 2

    engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

    total_pending = 0
    work: list[tuple[dict, list]] = []

    print("=== PRE-FLIGHT ===")

    for target in TARGETS:
        table = target["table"]
        pk = target["pk"]
        content_expr = target["content"]
        first = target["first"]
        last = target["last"]
        expected = target["expected"]

        with engine.connect() as conn:
            batch = conn.execute(
                text(
                    f"""
                    SELECT
                        COUNT(*) AS total,
                        MIN({pk}) AS min_id,
                        MAX({pk}) AS max_id
                    FROM {table}
                    WHERE {pk} BETWEEN :first_id AND :last_id
                    """
                ),
                {"first_id": first, "last_id": last},
            ).mappings().one()

            rows = conn.execute(
                text(
                    f"""
                    SELECT
                        {pk} AS id,
                        {content_expr} AS content
                    FROM {table}
                    WHERE {pk} BETWEEN :first_id AND :last_id
                      AND embedding IS NULL
                    ORDER BY {pk}
                    """
                ),
                {"first_id": first, "last_id": last},
            ).mappings().all()

        if (
            batch["total"] != expected
            or batch["min_id"] != first
            or batch["max_id"] != last
        ):
            print(
                f"{table}: RANGE GUARD FAILED. "
                f"Expected {expected} rows {first}-{last}; "
                f"found total={batch['total']} "
                f"range={batch['min_id']}-{batch['max_id']}",
                file=sys.stderr,
            )
            return 1

        pending = len(rows)
        total_pending += pending
        work.append((target, rows))

        print(
            f"{table}: rows={batch['total']}/{expected}, "
            f"NULL embeddings={pending}"
        )

    print(f"Total NULL embeddings to process: {total_pending}")
    print(
        f"Provider: {provider.name}/{provider.model} "
        f"({provider.dimension}-d)"
    )

    if total_pending == 0:
        print("Nothing to do. All target rows already embedded.")
        return 0

    total_done = 0

    for target, rows in work:
        table = target["table"]
        pk = target["pk"]
        first = target["first"]
        last = target["last"]

        print(f"\n=== EMBEDDING {table} {first}-{last} ===")

        done = 0

        for row in rows:
            vector = provider.embed(row["content"] or "")

            if len(vector) != EXPECTED_DIMENSION:
                print(
                    f"{table} {row['id']}: provider returned "
                    f"{len(vector)} dimensions",
                    file=sys.stderr,
                )
                return 1

            with engine.begin() as conn:
                result = conn.execute(
                    text(
                        f"""
                        UPDATE {table}
                        SET embedding = CAST(:vec AS vector),
                            embedding_model = :model,
                            embedding_dimension = :dimension,
                            embedding_version = :version
                        WHERE {pk} = :row_id
                          AND {pk} BETWEEN :first_id AND :last_id
                          AND embedding IS NULL
                        """
                    ),
                    {
                        "vec": vector_literal(vector),
                        "model": EXPECTED_MODEL,
                        "dimension": EXPECTED_DIMENSION,
                        "version": EXPECTED_VERSION,
                        "row_id": row["id"],
                        "first_id": first,
                        "last_id": last,
                    },
                )

            if result.rowcount != 1:
                print(
                    f"{table} {row['id']}: expected 1 update, "
                    f"got {result.rowcount}",
                    file=sys.stderr,
                )
                return 1

            done += 1
            total_done += 1

            if done % 25 == 0 or done == len(rows):
                print(f"{table}: {done}/{len(rows)}")

    print(
        f"\nEmbedding complete: "
        f"{total_done}/{total_pending} rows processed."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
