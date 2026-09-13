"""problems: record which Business DNA dimension each problem assesses

`GoXL_Business_DNA` Part 2 defines six pillars and twenty dimensions, and Part 3
scopes each stage BY DIMENSION -- "Pillars 1 and 6 partially apply (2 of 3
dimensions each)", "all 20 except Revenue Concentration and Hiring
Repeatability". None of that was expressible: a question's pillar was reachable
(questions.problem_id -> problems.pillar_id) and its dimension was not, so the
diagnosis scoped on the coarser axis and Part 3's dimension rules were recorded
in code as comments about what could not be enforced.

WHY ON `problems` AND NOT ON `questions`. Measured over both live snapshots this
repository carries (the shipped question batches and
scripts/calibration/bank_stage0.json), every problem falls in exactly one
category and every category in one pillar -- problem -> pillar is already
single-valued and is how the Business Health Score attributes an answer. A
dimension refines a pillar, so it belongs on the same row: 273 problems to
maintain instead of 3,340 questions, and dimension and pillar cannot contradict
each other for the same problem. The invariant that a dimension's pillar equals
its problem's pillar is checked at the end of upgrade() and reported.

NULLABLE, AND MOSTLY NULL AFTER THIS RUNS. That is the honest state, not an
unfinished one:

  * Part 2's twenty dimensions are a diagnostic lens over the six pillars, NOT a
    partition of the question bank. Whole families -- Marketing Execution (90
    questions), Sales Execution (90), Financial Management (120), Go-To-Market
    (116), Fundraising -- have no dimension among the twenty and never will
    unless Part 2 grows. NULL is their correct permanent value.
  * Several categories span three of their pillar's dimensions at once
    (Founder Psychology, Product, Team & Leadership), so assigning one would be
    fake precision. Those need the live problem names and subcategories, which
    this migration deliberately does not guess at.

So this backfills only what is a fact rather than a judgement: five categories
that map 1:1 onto a Part 2 dimension, each checked against real question text
in the shipped batches rather than inferred from the category name.

    Target Customer & ICP   -> customer_definition
    Competitive Awareness   -> competitive_awareness
    Business Model Design   -> revenue_model_clarity
    Business Planning       -> plan_to_vision_alignment
    Opportunity Evaluation  -> prioritization_discipline

TO FINISH THE JOB: scripts/backfill_problem_dimensions.py reports every problem
still unmapped, grouped by (pillar, category, subcategory), and applies a
reviewed assignment file. It is a content pass, not a code change.

NOTHING BREAKS WHILE MOST ROWS ARE NULL. app/api/v1/diagnosis/engine.py treats a
missing dimension as UNKNOWN and admits the question, leaning on the pillar and
category tests -- NULL never means "out of scope". The scope filters also refuse
to return an empty candidate set, so even a wholly wrong mapping degrades to
asking an off-topic question rather than ending a founder's diagnosis.

Revision ID: c3f7b28d5e91
Revises: b7e4f2a91c58
Create Date: 2026-09-12 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3f7b28d5e91"
down_revision: Union[str, Sequence[str], None] = "b7e4f2a91c58"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMN = "dimension_code"
_CONSTRAINT = "problems_dimension_code_check"
_INDEX = "idx_problems_dimension"

#: Part 2's twenty, as (code, pillar_id). The pillar is carried here so the
#: consistency check below does not need to import application code -- a
#: migration must keep working when the module it was written against moves.
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

#: The only assignments derivable without reading the live problem catalogue.
#: Mirrored by business_dna.DIMENSION_BY_CATEGORY, which a test pins to this.
_BACKFILL: tuple[tuple[str, str], ...] = (
    ("Target Customer & ICP", "customer_definition"),
    ("Competitive Awareness", "competitive_awareness"),
    ("Business Model Design", "revenue_model_clarity"),
    ("Business Planning", "plan_to_vision_alignment"),
    ("Opportunity Evaluation", "prioritization_discipline"),
)


def upgrade() -> None:
    bind = op.get_bind()

    op.add_column("problems", sa.Column(_COLUMN, sa.String(length=40), nullable=True))

    codes = ", ".join(f"'{code}'" for code, _ in _DIMENSIONS)
    op.execute(
        f"""
        ALTER TABLE problems
        ADD CONSTRAINT {_CONSTRAINT}
        CHECK ({_COLUMN} IS NULL OR {_COLUMN} IN ({codes}))
        """
    )
    op.execute(f"CREATE INDEX {_INDEX} ON problems ({_COLUMN})")

    # --- Backfill -----------------------------------------------------------
    # Only where dimension_code IS NULL, so a re-run after a content pass
    # cannot overwrite a reviewed assignment with the coarse category rule.
    for category, dimension_code in _BACKFILL:
        bind.execute(
            sa.text(
                f"UPDATE problems SET {_COLUMN} = :dim "
                f"WHERE category = :cat AND {_COLUMN} IS NULL"
            ),
            {"dim": dimension_code, "cat": category},
        )

    # --- Report -------------------------------------------------------------
    # The gap is stated, not assumed away: this column is useful in proportion
    # to how much of it is filled, and nothing else in the system will say so.
    mapped, total = bind.execute(
        sa.text(
            f"SELECT count({_COLUMN}), count(*) FROM problems"
        )
    ).one()
    print(
        f"  [{revision}] problems.{_COLUMN}: {mapped} of {total} mapped by the "
        f"category rules. The rest need a content pass -- run "
        f"scripts/backfill_problem_dimensions.py --report to see them grouped."
    )

    # A dimension whose pillar disagrees with its problem's pillar would move
    # answers between pillars in the Business Health Score. The five rules above
    # cannot cause it, but a reviewed assignment applied later can, and this
    # runs on every environment rather than only where the script was used.
    pairs = ", ".join(f"('{code}', {pillar})" for code, pillar in _DIMENSIONS)
    mismatched = bind.execute(
        sa.text(
            f"""
            SELECT count(*)
            FROM problems p
            JOIN (VALUES {pairs}) AS d(code, pillar_id) ON d.code = p.{_COLUMN}
            WHERE p.pillar_id IS DISTINCT FROM d.pillar_id
            """
        )
    ).scalar_one()
    if mismatched:
        print(
            f"  [{revision}] WARNING: {mismatched} problem(s) carry a dimension "
            "from a different pillar than their own pillar_id. The Business "
            "Health Score attributes by pillar_id, so these will score under "
            "one pillar and report under another. Reconcile before relying on "
            "dimension-level reporting."
        )


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {_INDEX}")
    op.execute(f"ALTER TABLE problems DROP CONSTRAINT IF EXISTS {_CONSTRAINT}")
    op.drop_column("problems", _COLUMN)
