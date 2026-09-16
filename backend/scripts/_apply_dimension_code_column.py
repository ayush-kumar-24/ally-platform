"""One-off: apply just the `problems.dimension_code` column directly.

`alembic upgrade head` cannot run against this database: its alembic_version
table points at a revision (f8a3c26e4b91) that does not exist anywhere in
this repo's migration history -- a pre-existing orphaned stamp, unrelated to
this branch, that needs its own reconciliation later. This script does not
touch alembic_version at all. It applies the exact, additive-only DDL from
alembic/versions/2026_09_12_1000-c3f7b28d5e91_problems_dimension_code.py
directly, idempotently (safe to re-run -- skips if the column already
exists), so the diagnosis engine's dimension scoping has something to read.

Usage:
    python -m scripts._apply_dimension_code_column --database-url "..." --confirm-writes
"""
from __future__ import annotations

import argparse
import sys

import sqlalchemy as sa

_COLUMN = "dimension_code"
_CONSTRAINT = "problems_dimension_code_check"
_INDEX = "idx_problems_dimension"

_DIMENSIONS: tuple[tuple[str, int], ...] = (
    ("skill_stage_fit", 1),
    ("time_allocation_reality", 1),
    ("founder_dependency", 1),
    ("problem_definition", 2),
    ("customer_definition", 2),
    ("competitive_awareness", 2),
    ("market_sizing_reality", 2),
    ("demand_reality", 3),
    ("revenue_model_clarity", 3),
    ("revenue_concentration", 3),
    ("pricing_confidence", 3),
    ("build_demand_alignment", 4),
    ("execution_velocity", 4),
    ("reliability_real_world", 4),
    ("team_structure_role_clarity", 5),
    ("decision_rights", 5),
    ("hiring_repeatability", 5),
    ("plan_to_vision_alignment", 6),
    ("prioritization_discipline", 6),
    ("institutional_memory", 6),
)

_BACKFILL: tuple[tuple[str, str], ...] = (
    ("Target Customer & ICP", "customer_definition"),
    ("Competitive Awareness", "competitive_awareness"),
    ("Business Model Design", "revenue_model_clarity"),
    ("Business Planning", "plan_to_vision_alignment"),
    ("Opportunity Evaluation", "prioritization_discipline"),
)


def run(args) -> int:
    engine = sa.create_engine(args.database_url, poolclass=sa.pool.NullPool)
    insp = sa.inspect(engine)
    existing = {c["name"] for c in insp.get_columns("problems")}

    if _COLUMN in existing:
        print(f"problems.{_COLUMN} already exists -- nothing to do.")
        return 0

    print(f"will add problems.{_COLUMN}, its check constraint, an index, "
          "and backfill 5 categories.")
    if not args.confirm_writes:
        print("Dry run. Re-run with --confirm-writes to apply.")
        return 0

    codes = ", ".join(f"'{code}'" for code, _ in _DIMENSIONS)
    with engine.begin() as conn:
        conn.execute(sa.text(
            f"ALTER TABLE problems ADD COLUMN {_COLUMN} VARCHAR(40)"
        ))
        conn.execute(sa.text(
            f"ALTER TABLE problems ADD CONSTRAINT {_CONSTRAINT} "
            f"CHECK ({_COLUMN} IS NULL OR {_COLUMN} IN ({codes}))"
        ))
        conn.execute(sa.text(f"CREATE INDEX {_INDEX} ON problems ({_COLUMN})"))

        for category, dimension_code in _BACKFILL:
            conn.execute(
                sa.text(
                    f"UPDATE problems SET {_COLUMN} = :dim "
                    f"WHERE category = :cat AND {_COLUMN} IS NULL"
                ),
                {"dim": dimension_code, "cat": category},
            )

        mapped, total = conn.execute(
            sa.text(f"SELECT count({_COLUMN}), count(*) FROM problems")
        ).one()
    print(f"done: {mapped} of {total} problems mapped by the category rules.")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--database-url", required=True)
    p.add_argument("--confirm-writes", action="store_true")
    args = p.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
