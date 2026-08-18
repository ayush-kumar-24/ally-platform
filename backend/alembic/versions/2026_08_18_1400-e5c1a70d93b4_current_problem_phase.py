"""Current Problem phase -- the third diagnosis section.

The Stage-Adaptive Diagnosis Framework doc defines three sections at every
stage: Founder DNA, Business DNA, Current Problem. The third was the only
one with no implementation at all.

Its shape (doc s3): "the founder states a symptom IN THEIR OWN WORDS; Ally
runs a short branching interrogation against the root-cause database to move
from stated symptom to actual root cause."

Two tables, mirroring founder_dna_questions/founder_dna_answers rather than
the `questions`/`answers` pair -- same reasoning as that migration: these
carry no root_cause_id/problem_id and are never scored against a root cause,
so they do not belong in the business diagnosis bank.

Deliberately NOT reusing founders.problem_statement (captured at onboarding
by frontend/src/pages/guided/Problem.jsx). That value can be months stale by
the time a diagnosis runs, and it feeds the separate "first impression"
feature -- overwriting it here would silently rewrite that feature's input.
The symptom is instead just the arc_position=0 row of this phase, so it is
timestamped by its own answer row and re-stated fresh at diagnosis time.

Guarded with the anchor-table check this project standardised on after
905bddfc6aff: production has been hand-patched before, so every DDL here
must be safe to re-run against a database that already has it.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e5c1a70d93b4"
down_revision = "d8b3f6c204ae"
branch_labels = None
depends_on = None

_STAGE_GROUPS = ("Stage 0", "Stage 0→1", "Stage 1→10+")


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _has_column(table: str, column: str) -> bool:
    if not _has_table(table):
        return False
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}
    return column in cols


def upgrade() -> None:
    if not _has_table("current_problem_questions"):
        op.create_table(
            "current_problem_questions",
            sa.Column("current_problem_question_id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("stage_group", sa.String(length=20), nullable=False),
            # 0 is the founder's own-words symptom statement; 1..n are the
            # doc's s4.x.c situational probes, asked in this order.
            sa.Column("arc_position", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("question_text", sa.Text(), nullable=False),
            sa.Column("is_symptom", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.CheckConstraint(
                "stage_group = ANY (ARRAY['Stage 0'::character varying, "
                "'Stage 0→1'::character varying, 'Stage 1→10+'::character varying]::text[])",
                name="current_problem_questions_stage_group_check",
            ),
            sa.PrimaryKeyConstraint("current_problem_question_id", name="current_problem_questions_pkey"),
        )
        op.create_index(
            "idx_current_problem_questions_stage",
            "current_problem_questions",
            ["stage_group", "arc_position"],
        )
        # Exactly one symptom question per stage -- the report quotes it
        # verbatim, so "which one did they state?" must never be ambiguous.
        # Same partial-unique trick as uq_founder_dna_one_closing_per_stage.
        op.create_index(
            "uq_current_problem_one_symptom_per_stage",
            "current_problem_questions",
            ["stage_group"],
            unique=True,
            postgresql_where=sa.text("is_symptom"),
        )

    if not _has_table("current_problem_answers"):
        op.create_table(
            "current_problem_answers",
            sa.Column("current_problem_answer_id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("founder_id", sa.Integer(), nullable=False),
            sa.Column("current_problem_question_id", sa.Integer(), nullable=False),
            sa.Column("answer_text", sa.Text(), nullable=False),
            sa.Column("answered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(
                ["founder_id"], ["founders.founder_id"],
                ondelete="CASCADE", name="current_problem_answers_founder_id_fkey",
            ),
            sa.ForeignKeyConstraint(
                ["current_problem_question_id"],
                ["current_problem_questions.current_problem_question_id"],
                name="current_problem_answers_question_id_fkey",
            ),
            sa.PrimaryKeyConstraint("current_problem_answer_id", name="current_problem_answers_pkey"),
        )
        op.create_index("idx_current_problem_answers_founder", "current_problem_answers", ["founder_id"])
        op.create_index(
            "uq_current_problem_answers_founder_question",
            "current_problem_answers",
            ["founder_id", "current_problem_question_id"],
            unique=True,
        )

    # Phase-completion marker, mirroring founder_dna_completed_at. This is
    # what /diagnosis/start gates on once this phase ships -- the symptom has
    # to exist before the root-cause interrogation it is supposed to steer.
    if not _has_column("founders", "current_problem_completed_at"):
        op.add_column(
            "founders",
            sa.Column("current_problem_completed_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    if _has_column("founders", "current_problem_completed_at"):
        op.drop_column("founders", "current_problem_completed_at")
    if _has_table("current_problem_answers"):
        op.drop_table("current_problem_answers")
    if _has_table("current_problem_questions"):
        op.drop_table("current_problem_questions")
