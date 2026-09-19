"""The capability taxonomy -- the shared vocabulary for evidence, targets and actions.

Hand-modelled rather than generated, for the same reason as `memory.py`,
`suggestions.py` and `session_context.py`: `schema.py` is a snapshot of the live
database and these tables are newer than that snapshot.

Read the migration f2a91c3d7b58 for why this is a NEW vocabulary rather than a
reuse of `interventions.capability_domain` (390 near-unique free-text labels),
`readiness_pillars` (scoring axes) or `interventions.section` (subject areas).

Nothing in the application reads these tables yet. They are the foundation Step
6 (capability_requirements), Step 8 (capability_evidence) and Step 9 (the Gap
Engine) are built on, and they are seeded and tested now so those steps inherit
a reviewed vocabulary rather than inventing one under deadline.
"""

from __future__ import annotations

import datetime
from typing import Any, Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    PrimaryKeyConstraint,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class CapabilityDomain(Base):
    """A small, stable grouping of capabilities. Seven of them, and no more
    without a deliberate decision -- the taxonomy's value is in being short
    enough to hold in your head."""

    __tablename__ = "capability_domains"
    __table_args__ = (
        PrimaryKeyConstraint("domain_id", name="capability_domains_pkey"),
        UniqueConstraint("domain_code", name="capability_domains_domain_code_key"),
    )

    domain_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    domain_code: Mapped[str] = mapped_column(String(20), nullable=False)
    domain_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    domain_order: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(True), nullable=False, server_default=text("now()"))

    capabilities: Mapped[list["Capability"]] = relationship(
        "Capability", back_populates="domain")


class Capability(Base):
    """One durable thing a business can or cannot do.

    Industry-neutral by construction: there is no SaaS variant and no
    agriculture variant of a capability. Context (industry x business model x
    stage x target scale) belongs on the REQUIREMENT, which Step 6 adds.
    """

    __tablename__ = "capabilities"
    __table_args__ = (
        PrimaryKeyConstraint("capability_id", name="capabilities_pkey"),
        UniqueConstraint("capability_code", name="capabilities_capability_code_key"),
        ForeignKeyConstraint(["domain_id"], ["capability_domains.domain_id"],
                             name="capabilities_domain_id_fkey"),
        ForeignKeyConstraint(["pillar_id"], ["readiness_pillars.pillar_id"],
                             name="capabilities_pillar_id_fkey"),
        Index("idx_capabilities_domain", "domain_id"),
    )

    capability_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    capability_code: Mapped[str] = mapped_column(String(30), nullable=False)
    domain_id: Mapped[int] = mapped_column(Integer, nullable=False)
    capability_name: Mapped[str] = mapped_column(String(120), nullable=False)
    #: Contextual metadata only. Says which existing scoring axis this
    #: capability reads against so a report can group under a heading founders
    #: already see. Nullable, and nothing gates on it -- pillars measure the
    #: founder today, capabilities describe what the business can do.
    pillar_id: Mapped[Optional[int]] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(True), nullable=False, server_default=text("now()"))

    domain: Mapped["CapabilityDomain"] = relationship(
        "CapabilityDomain", back_populates="capabilities")
    criteria: Mapped[list["CapabilityEvidenceCriterion"]] = relationship(
        "CapabilityEvidenceCriterion", back_populates="capability",
        order_by="CapabilityEvidenceCriterion.criterion_order")


class CapabilityEvidenceCriterion(Base):
    """An observable statement about the business, used to judge a capability.

    Statements, never scores and never advice: "Someone other than the founder
    closes business" is a thing an assessor can agree or disagree with. The
    LEVEL a set of criteria implies is decided by
    `app/api/v1/diagnosis/capability_levels.py`, not stored per criterion --
    one scale for every capability is what makes observations comparable to
    requirements.
    """

    __tablename__ = "capability_evidence_criteria"
    __table_args__ = (
        PrimaryKeyConstraint("criterion_id", name="capability_evidence_criteria_pkey"),
        ForeignKeyConstraint(["capability_id"], ["capabilities.capability_id"],
                             ondelete="CASCADE",
                             name="capability_evidence_criteria_capability_id_fkey"),
        UniqueConstraint("capability_id", "criterion_order",
                         name="uq_capability_evidence_criteria_order"),
    )

    criterion_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    capability_id: Mapped[int] = mapped_column(Integer, nullable=False)
    criterion_text: Mapped[str] = mapped_column(Text, nullable=False)
    criterion_order: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(True), nullable=False, server_default=text("now()"))

    capability: Mapped["Capability"] = relationship("Capability", back_populates="criteria")


class InterventionCapability(Base):
    """Which capability an intervention BUILDS.

    The composite primary key is the uniqueness rule: one intervention may build
    several capabilities, but never the same one twice.
    """

    __tablename__ = "intervention_capabilities"
    __table_args__ = (
        PrimaryKeyConstraint("intervention_id", "capability_id",
                             name="intervention_capabilities_pkey"),
        ForeignKeyConstraint(["intervention_id"], ["interventions.intervention_id"],
                             ondelete="CASCADE",
                             name="intervention_capabilities_intervention_id_fkey"),
        ForeignKeyConstraint(["capability_id"], ["capabilities.capability_id"],
                             ondelete="CASCADE",
                             name="intervention_capabilities_capability_id_fkey"),
        Index("idx_intervention_capabilities_capability", "capability_id"),
    )

    intervention_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    capability_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(True), nullable=False, server_default=text("now()"))


class QuestionCapability(Base):
    """Which capability a question provides EVIDENCE about.

    Intentionally empty. Mapping ~3,460 questions is a curation pass, and a
    fabricated mapping would produce confident evidence about capabilities
    nobody checked. An unmapped question simply yields no capability evidence --
    the same fail-open every other optional map in this codebase uses.
    """

    __tablename__ = "question_capabilities"
    __table_args__ = (
        PrimaryKeyConstraint("question_id", "capability_id",
                             name="question_capabilities_pkey"),
        ForeignKeyConstraint(["question_id"], ["questions.question_id"],
                             ondelete="CASCADE",
                             name="question_capabilities_question_id_fkey"),
        ForeignKeyConstraint(["capability_id"], ["capabilities.capability_id"],
                             ondelete="CASCADE",
                             name="question_capabilities_capability_id_fkey"),
        Index("idx_question_capabilities_capability", "capability_id"),
    )

    question_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    capability_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(True), nullable=False, server_default=text("now()"))


class CapabilityRequirement(Base):
    """What a destination requires -- the Target-State Knowledge Base.

    CURATED REFERENCE DATA. Seeded by migration a8d34f7e2b91 and dumped like the
    question bank; nothing generates a row at runtime and nothing may. Letting
    an LLM invent requirements would make the destination's demands depend on a
    sampling temperature, and a founder could not be shown why.

    Every context dimension is nullable and NULL means WILDCARD -- "applies
    whatever this founder's value is". It does NOT mean "applies when unknown":
    a founder whose industry we never asked about matches the NULL-industry rows
    and none of the specific ones, so an incomplete profile yields a more
    generic requirement set, never an empty one.

    `from_stage_order` is an inclusive LOWER BOUND rather than an exact match,
    so the table needs no row per stage. The resolver breaks a specificity tie
    on the tightest bound -- see app/api/v1/diagnosis/target_state.py, which
    owns the cascade.
    """

    __tablename__ = "capability_requirements"
    __table_args__ = (
        PrimaryKeyConstraint("requirement_id", name="capability_requirements_pkey"),
        ForeignKeyConstraint(["capability_id"], ["capabilities.capability_id"],
                             ondelete="CASCADE",
                             name="capability_requirements_capability_id_fkey"),
        CheckConstraint("required_level BETWEEN 0 AND 3",
                        name="capability_requirements_required_level_check"),
        CheckConstraint("necessity IN ('core', 'contextual')",
                        name="capability_requirements_necessity_check"),
        CheckConstraint("from_stage_order IS NULL OR from_stage_order BETWEEN 1 AND 8",
                        name="capability_requirements_from_stage_order_check"),
        UniqueConstraint(
            "capability_id", "industry_code", "business_model", "from_stage_order",
            "target_revenue_band", "target_time_horizon",
            name="uq_capability_requirements_context",
            postgresql_nulls_not_distinct=True,
        ),
        Index("idx_capability_requirements_capability", "capability_id"),
        Index("idx_capability_requirements_band", "target_revenue_band"),
    )

    requirement_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    capability_id: Mapped[int] = mapped_column(Integer, nullable=False)
    industry_code: Mapped[Optional[str]] = mapped_column(String(20))
    business_model: Mapped[Optional[str]] = mapped_column(String(100))
    from_stage_order: Mapped[Optional[int]] = mapped_column(Integer)
    target_revenue_band: Mapped[Optional[str]] = mapped_column(String(50))
    target_time_horizon: Mapped[Optional[str]] = mapped_column(String(30))
    #: CapabilityLevel 0-3. Stored as a small int rather than an enum type so
    #: the scale lives in exactly one place (capability_levels.py).
    required_level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    necessity: Mapped[str] = mapped_column(String(16), nullable=False)
    #: Shown to the founder. NOT NULL: a requirement nobody can explain is a
    #: rule nobody can challenge.
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    source_document: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(True), nullable=False, server_default=text("now()"))


class CapabilityEvidence(Base):
    """One OBSERVATION, never an assessment. See migration e6b3f92a1c48.

    UNASSESSED is represented by the ABSENCE of a row, not a value in one --
    there is no NULL `observed_level` and no sentinel row. Every row that
    exists here passed the extractor's own bar for "this answer confidently
    supports a specific level"; a hedge or a failed extraction produces no row
    at all rather than one with a low confidence and a guessed level.

    One row per answer (UNIQUE on answer_id), because question_capabilities
    already guarantees a question maps to at most one capability. Multiple
    observations about the SAME capability from DIFFERENT answers are
    independent rows -- aggregating them into one current-state reading is
    Step 7C, and it is designed to need exactly these rows, unmodified, to do
    it conservatively later.
    """

    __tablename__ = "capability_evidence"
    __table_args__ = (
        PrimaryKeyConstraint("evidence_id", name="capability_evidence_pkey"),
        ForeignKeyConstraint(["capability_id"], ["capabilities.capability_id"],
                             ondelete="CASCADE",
                             name="capability_evidence_capability_id_fkey"),
        ForeignKeyConstraint(["question_id"], ["questions.question_id"],
                             ondelete="CASCADE",
                             name="capability_evidence_question_id_fkey"),
        ForeignKeyConstraint(["answer_id"], ["answers.answer_id"],
                             ondelete="CASCADE",
                             name="capability_evidence_answer_id_fkey"),
        # Composite: a stored criterion_id must belong to the SAME capability_id
        # on this row. MATCH SIMPLE (Postgres default) means a NULL criterion_id
        # always satisfies this -- only a non-NULL, cross-capability value is
        # ever rejected.
        ForeignKeyConstraint(
            ["capability_id", "criterion_id"],
            ["capability_evidence_criteria.capability_id",
             "capability_evidence_criteria.criterion_id"],
            ondelete="SET NULL", name="capability_evidence_criterion_fkey",
        ),
        CheckConstraint("observed_level BETWEEN 0 AND 3",
                        name="capability_evidence_observed_level_check"),
        CheckConstraint("confidence >= 0 AND confidence <= 1",
                        name="capability_evidence_confidence_check"),
        UniqueConstraint("answer_id", name="uq_capability_evidence_answer"),
        Index("idx_capability_evidence_capability", "capability_id"),
        Index("idx_capability_evidence_question", "question_id"),
    )

    evidence_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    capability_id: Mapped[int] = mapped_column(Integer, nullable=False)
    question_id: Mapped[int] = mapped_column(Integer, nullable=False)
    answer_id: Mapped[int] = mapped_column(Integer, nullable=False)
    #: Nullable: confident THAT a capability was evidenced without being
    #: confident WHICH of its four criteria the answer specifically speaks to
    #: is still a real, storable observation.
    criterion_id: Mapped[Optional[int]] = mapped_column(Integer)
    #: CapabilityLevel 0-3 (app/api/v1/diagnosis/capability_levels.py). Never
    #: NULL -- see the class docstring.
    observed_level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    #: Confidence in THIS OBSERVATION, not founder risk, not diagnosis
    #: confidence, not root-cause confidence. A different number for a
    #: different question.
    confidence: Mapped[Any] = mapped_column(Numeric(3, 2), nullable=False)
    evidence_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(True), nullable=False, server_default=text("now()"))
