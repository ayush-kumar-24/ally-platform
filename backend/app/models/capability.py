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
from typing import Optional

from sqlalchemy import (
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    PrimaryKeyConstraint,
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
