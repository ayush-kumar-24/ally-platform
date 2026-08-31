import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from sqlalchemy import create_engine, text

from app.core.config import settings


FIRST_ID = 2130
LAST_ID = 2229
EXPECTED_QUESTIONS = 100
EXPECTED_TAG_MAPPINGS = 275
EXPECTED_DIMENSION = 1536
EXPECTED_MODEL = "text-embedding-3-small"
EXPECTED_VERSION = "openai-3-small-v1"


def main() -> int:
    engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT
                    COUNT(*) AS total,
                    MIN(question_id) AS min_id,
                    MAX(question_id) AS max_id,
                    COUNT(*) FILTER (WHERE embedding IS NULL) AS null_embeddings,
                    COUNT(*) FILTER (
                        WHERE embedding IS NOT NULL
                        AND vector_dims(embedding) <> :dimension
                    ) AS bad_dimensions,
                    COUNT(*) FILTER (
                        WHERE embedding_model IS DISTINCT FROM :model
                    ) AS bad_models,
                    COUNT(*) FILTER (
                        WHERE embedding_version IS DISTINCT FROM :version
                    ) AS bad_versions
                FROM questions
                WHERE question_id BETWEEN :first_id AND :last_id
                """
            ),
            {
                "first_id": FIRST_ID,
                "last_id": LAST_ID,
                "dimension": EXPECTED_DIMENSION,
                "model": EXPECTED_MODEL,
                "version": EXPECTED_VERSION,
            },
        ).mappings().one()

        tag_count = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM question_tag_mapping
                WHERE question_id BETWEEN :first_id AND :last_id
                """
            ),
            {"first_id": FIRST_ID, "last_id": LAST_ID},
        ).scalar_one()

    failures = []

    if row["total"] != EXPECTED_QUESTIONS:
        failures.append(
            f"questions: expected {EXPECTED_QUESTIONS}, found {row['total']}"
        )

    if row["min_id"] != FIRST_ID or row["max_id"] != LAST_ID:
        failures.append(
            f"ID range: expected {FIRST_ID}-{LAST_ID}, "
            f"found {row['min_id']}-{row['max_id']}"
        )

    if tag_count != EXPECTED_TAG_MAPPINGS:
        failures.append(
            f"tag mappings: expected {EXPECTED_TAG_MAPPINGS}, found {tag_count}"
        )

    if row["null_embeddings"] != 0:
        failures.append(f"NULL embeddings: {row['null_embeddings']}")

    if row["bad_dimensions"] != 0:
        failures.append(f"bad embedding dimensions: {row['bad_dimensions']}")

    if row["bad_models"] != 0:
        failures.append(f"bad embedding models: {row['bad_models']}")

    if row["bad_versions"] != 0:
        failures.append(f"bad embedding versions: {row['bad_versions']}")

    print(f"Questions: {row['total']}/{EXPECTED_QUESTIONS}")
    print(f"ID range: {row['min_id']}-{row['max_id']}")
    print(f"Tag mappings: {tag_count}/{EXPECTED_TAG_MAPPINGS}")
    print(f"NULL embeddings: {row['null_embeddings']}")
    print(f"Bad dimensions: {row['bad_dimensions']}")
    print(f"Bad models: {row['bad_models']}")
    print(f"Bad versions: {row['bad_versions']}")

    if failures:
        print("\nVERIFY FAILED")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("\nVERIFY PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
