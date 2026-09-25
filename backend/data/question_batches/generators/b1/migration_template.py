"""batch 1: industries 1-5 (A-Z order) pillar + dimension fill

Revision ID: REPLACE_ME
Revises: c9f41b8e3a07
Create Date: REPLACE_ME

Adds the problem -> root cause -> question -> intervention chain for the three
pillars the industry layer never covered, for agritech, automotive, fintech,
beauty_personal_care and proptech -- industries 1-5 in the agreed A-Z order.

Measured before this migration, across all 30 industries:
    Strategic Clarity    0 industry problems
    Founder Readiness    2
    Team & Leadership   14
(Revenue Maturity 171, Market Clarity 142, Product & Execution 121.)

Because the diagnosis opening block forces the first 12 questions to be
industry-specific, the starved pillars could not be assessed from the industry
bank at all. Beauty & Personal Care held all 15 of its problems in Market
Clarity; foodtech held 11 of 15 in Revenue Maturity.

IDEMPOTENT. Every insert is ON CONFLICT DO NOTHING on its unique code, and the
ids are explicit and allocated above the maxima this migration was written
against (problems 900-944, root_causes 4300-4434, questions 5500-5769,
interventions 1200-1289). Re-running changes nothing. Verified by applying the
SQL twice against a database built from zero.

The SQL lives beside this file so the same bytes can be handed to a DBA and run
directly with psql -- Supabase and RDS both take it unchanged.
"""

from pathlib import Path

from alembic import op

revision = "REPLACE_ME"
down_revision = "c9f41b8e3a07"
branch_labels = None
depends_on = None

_SQL = Path(__file__).resolve().parents[2] / "data" / "question_batches" / "batch1_industries_1to5.sql"


def _statements(text: str) -> list[str]:
    """Split on semicolons at end of line only.

    Deliberately NOT a bare text.split(";"): the seed files carry semicolons
    inside quoted prose, and two existing migrations (63340a6e5fdb and
    74e6b0317802) split naively and cannot build a database from zero as a
    result -- 74e6b0317802 fails with "can't execute an empty query" on its
    leading comment block. Statements here are emitted one per line, so
    splitting on ";\n" is both correct and cheap. Comment-only chunks are
    dropped rather than executed.
    """
    out = []
    for raw in text.split(";\n"):
        stripped = "\n".join(
            line for line in raw.splitlines() if not line.strip().startswith("--")
        ).strip()
        if stripped:
            out.append(stripped)
    return out


def upgrade() -> None:
    if not _SQL.exists():
        raise RuntimeError(f"Batch file not found: {_SQL}")
    bind = op.get_bind()
    for statement in _statements(_SQL.read_text(encoding="utf-8-sig")):
        if statement.upper().startswith(("BEGIN", "COMMIT")):
            continue  # alembic already runs inside a transaction
        bind.exec_driver_sql(statement)


def downgrade() -> None:
    bind = op.get_bind()
    # Child rows first. Ranges match the explicit ids in the batch file.
    bind.exec_driver_sql(
        "delete from question_industry_mapping where question_id between 5500 and 5769"
    )
    bind.exec_driver_sql("delete from questions where question_id between 5500 and 5769")
    bind.exec_driver_sql(
        "delete from interventions where intervention_id between 1200 and 1289"
    )
    bind.exec_driver_sql("delete from root_causes where root_cause_id between 4300 and 4434")
    bind.exec_driver_sql("delete from problems where problem_id between 900 and 944")
