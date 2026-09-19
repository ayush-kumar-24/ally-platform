"""capability_evidence: one row per OBSERVATION, never an assessment.

FOUNDER ANSWER -> CAPABILITY EVIDENCE, and nothing past it. This table is the
whole of Step 7B: it preserves what an answer observably said about a
capability, traceably, and stops there. It does not score a capability, does
not aggregate observations, does not compare anything to a target requirement,
and is read by nothing outside this migration and the extractor that writes it.

OBSERVATION, NOT ASSESSMENT. `Q1 -> FND-DELEG -> Level 1`, `Q2 -> FND-DELEG ->
Level 2`, `Q3 -> FND-DELEG -> Level 1` are three rows, not one. Averaging or
picking a "final" level is Step 7C's job (the conservative "lowest confident
reading" aggregation), and it needs the individual rows intact to do it -- so
this table is designed to be read many-rows-per-capability, never overwritten
in place.

NO EVIDENCE IS NOT LEVEL 0, and this is enforced by ABSENCE rather than by a
sentinel. There is no "unassessed" row: a capability nobody has evidence for
simply has no rows in this table, exactly as capability_requirements has no row
answering a wildcard doesn't apply to yet. `observed_level` is NOT NULL because
every row that exists here IS evidence -- if an answer could not confidently
support a criterion, the extractor stores nothing at all rather than a row with
a hedged or null level. See app/api/v1/diagnosis/capability_levels.py, whose
CapabilityLevel enum this column reuses (0 absent / 1 personal / 2 documented /
3 owned) -- not a new scale invented for this table.

ONE ROW PER ANSWER. `question_capabilities` already established that a question
maps to at most one capability (Step 7A: zero questions map to two), so one
answer can produce at most one observation. The UNIQUE constraint on `answer_id`
is therefore both the idempotency guard section 11 of the step brief asks for
AND a direct expression of that 1A0-question 1-capability invariant -- not an
arbitrary choice among several plausible keys.

TRACEABILITY IS FOUR COLUMNS, NOT A JOIN CHAIN. capability_id, question_id,
answer_id and criterion_id (nullable) all live on the row itself, so "why did
Ally think GTM-OWN was level 1" is answered by one SELECT, not a chain of joins
through tables that could themselves change. question_id is technically
derivable from answer_id -> answers.question_id, but denormalising it here is
what the step brief's own traceability chain (section 8) asks for, and it means
this table still says something coherent if an answer row is ever archived.

criterion_id IS CROSS-CHECKED AGAINST capability_id AT THE DATABASE, not just in
application code. `capability_evidence_criteria` gets a new UNIQUE
(capability_id, criterion_id) here -- trivially true since criterion_id is
already a global primary key, but it is what lets this table's FK be a
COMPOSITE (capability_id, criterion_id) reference. Postgres's default MATCH
SIMPLE means the whole FK is satisfied whenever criterion_id IS NULL (the common
case: no criterion confidently identified), and enforced whenever it is not --
so a mapping to the wrong capability's criterion cannot be stored, ever, without
a second query.

Purely additive: no existing table is altered except the new UNIQUE constraint
on capability_evidence_criteria, which touches no row and no existing query.
"""

from alembic import op
import sqlalchemy as sa

revision = "e6b3f92a1c48"
down_revision = "d1a4c8e2f907"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enables the composite FK below. criterion_id is already globally unique
    # (it is capability_evidence_criteria's own primary key), so this adds no
    # new uniqueness the data doesn't already have -- it only lets a SECOND
    # table reference the PAIR.
    op.create_unique_constraint(
        "uq_capability_evidence_criteria_capability_criterion",
        "capability_evidence_criteria",
        ["capability_id", "criterion_id"],
    )

    op.create_table(
        "capability_evidence",
        sa.Column("evidence_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("capability_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("answer_id", sa.Integer(), nullable=False),
        # Nullable: an extractor may be confident THAT a capability was
        # evidenced without being confident WHICH of its four criteria the
        # answer specifically speaks to. A capability-level observation with no
        # criterion attached is still a real, storable observation.
        sa.Column("criterion_id", sa.Integer(), nullable=True),
        # CapabilityLevel 0-3 (capability_levels.py). Never NULL: an unassessed
        # capability has no row, not a row with no level.
        sa.Column("observed_level", sa.SmallInteger(), nullable=False),
        # Confidence in THIS EXTRACTED OBSERVATION -- not diagnostic risk, not
        # the founder's answer quality, not root-cause or overall diagnosis
        # confidence. Those are different numbers computed by different code for
        # different reasons; this one answers "how sure is the extractor that
        # this observation is right".
        sa.Column("confidence", sa.Numeric(3, 2), nullable=False),
        # The normalised, human-readable observation -- what a report or a
        # debugging session shows to explain the level. Not the raw answer text
        # verbatim (that is available via answer_id) but the extractor's
        # statement of what it saw, e.g. "founder personally closes nearly every
        # deal; no one else is described as owning sales."
        sa.Column("evidence_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("evidence_id", name="capability_evidence_pkey"),
        sa.ForeignKeyConstraint(["capability_id"], ["capabilities.capability_id"],
                                ondelete="CASCADE",
                                name="capability_evidence_capability_id_fkey"),
        sa.ForeignKeyConstraint(["question_id"], ["questions.question_id"],
                                ondelete="CASCADE",
                                name="capability_evidence_question_id_fkey"),
        sa.ForeignKeyConstraint(["answer_id"], ["answers.answer_id"],
                                ondelete="CASCADE",
                                name="capability_evidence_answer_id_fkey"),
        # Composite, matching (capability_id, criterion_id) on
        # capability_evidence_criteria. MATCH SIMPLE (Postgres's default) means
        # a NULL criterion_id satisfies this trivially; a non-NULL one must name
        # a criterion that actually belongs to the same capability_id.
        sa.ForeignKeyConstraint(
            ["capability_id", "criterion_id"],
            ["capability_evidence_criteria.capability_id",
             "capability_evidence_criteria.criterion_id"],
            ondelete="SET NULL",
            name="capability_evidence_criterion_fkey",
        ),
        sa.CheckConstraint("observed_level BETWEEN 0 AND 3",
                           name="capability_evidence_observed_level_check"),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1",
                           name="capability_evidence_confidence_check"),
        # Idempotency: one observation per answer. Also the direct database
        # expression of "a question maps to at most one capability" (Step 7A).
        sa.UniqueConstraint("answer_id", name="uq_capability_evidence_answer"),
    )
    op.create_index("idx_capability_evidence_capability", "capability_evidence",
                    ["capability_id"])
    op.create_index("idx_capability_evidence_question", "capability_evidence",
                    ["question_id"])


def downgrade() -> None:
    op.drop_index("idx_capability_evidence_question", table_name="capability_evidence")
    op.drop_index("idx_capability_evidence_capability", table_name="capability_evidence")
    op.drop_table("capability_evidence")
    op.drop_constraint(
        "uq_capability_evidence_criteria_capability_criterion",
        "capability_evidence_criteria", type_="unique",
    )
