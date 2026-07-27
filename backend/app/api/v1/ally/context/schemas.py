"""Typed, immutable context DTOs for the Ally AI layer.

`AllyContext` is the single grounding object every Phase-5 component consumes. It
is assembled ONLY from persisted diagnosis outputs -- nothing here recomputes a
score. Every field is optional-honest: when the diagnosis has not produced a
value, the field is None rather than a guessed default, and `is_answerable`
tells downstream layers whether there is enough context to respond at all.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Mapping

# Structural version of the AllyContext DTO -- NOT a business-logic version. Bump
# this only when the SHAPE of the context changes (a field added/removed/retyped),
# so downstream consumers (Prompt Manager, Memory, RAG, Router, Orchestrator) can
# branch on the structure they were built against and evolve without breaking.
ALLY_CONTEXT_SCHEMA_VERSION = "v1"


@dataclass(frozen=True)
class FounderProfileContext:
    founder_id: int
    full_name: str | None
    stage_id: int | None
    stage_name: str | None
    industry: str | None


@dataclass(frozen=True)
class RootCauseContext:
    root_cause_id: int
    code: str | None
    name: str
    category: str | None
    rank: int
    confirmation_status: str
    weighted_score: Decimal
    is_top_finding: bool


@dataclass(frozen=True)
class BusinessHealthContext:
    overall_score: str | None            # persisted as string in the report dict
    band: str | None
    pillars: tuple[Mapping[str, Any], ...]  # raw pillar dicts from the report
    red_flags: tuple[str, ...]


@dataclass(frozen=True)
class DiagnosisContext:
    session_id: int
    overall_confidence: Decimal | None
    routing_state: str | None
    distress_mode: bool
    session_state: str | None
    executive_summary: str | None
    priority_actions: tuple[str, ...]
    next_steps: tuple[str, ...]


@dataclass(frozen=True)
class InternalIntelligenceContext:
    psychological_state: str | None
    distress_signals: tuple[Mapping[str, Any], ...]
    consultant_notes: str | None         # internal_notes markdown (consultant-only)
    blind_spot_ids: tuple[int, ...]


@dataclass(frozen=True)
class AllyContext:
    """Everything the AI may ground an answer on, for one founder (+ session).

    `has_diagnosis` is False when no active founder report exists yet; in that
    case `diagnosis`, `business_health` and `internal_intelligence` are None and
    `root_causes` is empty. `is_answerable` is the gate downstream layers check
    before responding -- the AI must not answer diagnosis questions without it.
    """

    founder: FounderProfileContext
    has_diagnosis: bool
    # Structure version of this DTO, carried on every instance so every downstream
    # consumer receives it automatically. Defaulted, so no construction site needs
    # to set it. See ALLY_CONTEXT_SCHEMA_VERSION.
    schema_version: str = ALLY_CONTEXT_SCHEMA_VERSION
    diagnosis: DiagnosisContext | None = None
    root_causes: tuple[RootCauseContext, ...] = field(default_factory=tuple)
    business_health: BusinessHealthContext | None = None
    internal_intelligence: InternalIntelligenceContext | None = None
    report_id: int | None = None
    generated_at: datetime | None = None

    @property
    def is_answerable(self) -> bool:
        """True when there is a diagnosis to ground an answer on. Downstream AI
        layers MUST refuse diagnosis-grounded answers when this is False."""
        return self.has_diagnosis and self.diagnosis is not None

    @property
    def is_distress(self) -> bool:
        """Wellbeing-first signal: surfaces distress from the frozen diagnosis so
        the orchestrator can lead with the distress path (never suppressed)."""
        return bool(self.diagnosis and self.diagnosis.distress_mode)
