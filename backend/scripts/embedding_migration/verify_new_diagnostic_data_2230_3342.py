from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from sqlalchemy import create_engine, text

from app.core.config import settings


EXPECTED_DIMENSION = 1536
EXPECTED_MODEL = "text-embedding-3-small"
EXPECTED_VERSION = "openai-3-small-v1"

QUESTION_FIRST = 2230
QUESTION_LAST = 3342
EXPECTED_QUESTIONS = 1113
EXPECTED_MAPPINGS = 1431

TARGETS = [
    {
        "table": "questions",
        "pk": "question_id",
        "first": 2230,
        "last": 3342,
        "expected": 1113,
    },
    {
        "table": "problems",
        "pk": "problem_id",
        "first": 270,
        "last": 275,
        "expected": 6,
    },
    {
        "table": "root_causes",
        "pk": "root_cause_id",
        "first": 1976,
        "last": 2011,
        "expected": 36,
    },
]


def main() -> int:
    engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

    failed = False
    zero_vector = "[" + ",".join(["0"] * EXPECTED_DIMENSION) + "]"

    print("=== NEW DIAGNOSTIC DATA VERIFICATION ===")

    with engine.connect() as conn:
        # Reference-data guards.
        references = [
            ("question_tags", "tag_id", 79, 88, 10),
            ("problems", "problem_id", 270, 275, 6),
            ("root_causes", "root_cause_id", 1976, 2011, 36),
        ]

        for table, pk, first, last, expected in references:
            row = conn.execute(
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

            ok = (
                row["total"] == expected
                and row["min_id"] == first
                and row["max_id"] == last
            )

            print(
                f"{table}: "
                f"{row['total']}/{expected}, "
                f"range={row['min_id']}-{row['max_id']} "
                f"{'PASS' if ok else 'FAIL'}"
            )

            if not ok:
                failed = True

        # Question count/range.
        questions = conn.execute(
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
            {
                "first_id": QUESTION_FIRST,
                "last_id": QUESTION_LAST,
            },
        ).mappings().one()

        question_ok = (
            questions["total"] == EXPECTED_QUESTIONS
            and questions["min_id"] == QUESTION_FIRST
            and questions["max_id"] == QUESTION_LAST
        )

        print(
            f"questions: {questions['total']}/{EXPECTED_QUESTIONS}, "
            f"range={questions['min_id']}-{questions['max_id']} "
            f"{'PASS' if question_ok else 'FAIL'}"
        )

        if not question_ok:
            failed = True

        # Mapping count.
        mappings = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM question_tag_mapping
                WHERE question_id BETWEEN :first_id AND :last_id
                """
            ),
            {
                "first_id": QUESTION_FIRST,
                "last_id": QUESTION_LAST,
            },
        ).scalar()

        mapping_ok = mappings == EXPECTED_MAPPINGS

        print(
            f"question_tag_mapping: "
            f"{mappings}/{EXPECTED_MAPPINGS} "
            f"{'PASS' if mapping_ok else 'FAIL'}"
        )

        if not mapping_ok:
            failed = True

        print("\n=== EMBEDDINGS ===")

        for target in TARGETS:
            table = target["table"]
            pk = target["pk"]
            first = target["first"]
            last = target["last"]
            expected = target["expected"]

            result = conn.execute(
                text(
                    f"""
                    SELECT
                        COUNT(*) AS total,

                        COUNT(*) FILTER (
                            WHERE embedding IS NULL
                        ) AS null_embeddings,

                        COUNT(*) FILTER (
                            WHERE embedding IS NOT NULL
                              AND vector_dims(embedding) <> :dimension
                        ) AS wrong_dimensions,

                        COUNT(*) FILTER (
                            WHERE embedding_model IS DISTINCT FROM :model
                        ) AS wrong_models,

                        COUNT(*) FILTER (
                            WHERE embedding_version IS DISTINCT FROM :version
                        ) AS wrong_versions,

                        COUNT(*) FILTER (
                            WHERE embedding_dimension IS DISTINCT FROM :dimension
                        ) AS wrong_dimension_metadata,

                        COUNT(*) FILTER (
                            WHERE embedding IS NOT NULL
                              AND embedding = CAST(:zero_vector AS vector)
                        ) AS zero_vectors

                    FROM {table}
                    WHERE {pk} BETWEEN :first_id AND :last_id
                    """
                ),
                {
                    "first_id": first,
                    "last_id": last,
                    "dimension": EXPECTED_DIMENSION,
                    "model": EXPECTED_MODEL,
                    "version": EXPECTED_VERSION,
                    "zero_vector": zero_vector,
                },
            ).mappings().one()

            ok = (
                result["total"] == expected
                and result["null_embeddings"] == 0
                and result["wrong_dimensions"] == 0
                and result["wrong_models"] == 0
                and result["wrong_versions"] == 0
                and result["wrong_dimension_metadata"] == 0
                and result["zero_vectors"] == 0
            )

            print(
                f"{table}: "
                f"rows={result['total']}/{expected}, "
                f"NULL={result['null_embeddings']}, "
                f"bad_dim={result['wrong_dimensions']}, "
                f"bad_model={result['wrong_models']}, "
                f"bad_version={result['wrong_versions']}, "
                f"bad_metadata={result['wrong_dimension_metadata']}, "
                f"zero_vectors={result['zero_vectors']} "
                f"{'PASS' if ok else 'FAIL'}"
            )

            if not ok:
                failed = True

    print()

    if failed:
        print("FINAL VERIFICATION: FAIL", file=sys.stderr)
        return 1

    print("FINAL VERIFICATION: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
