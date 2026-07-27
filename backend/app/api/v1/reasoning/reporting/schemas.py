"""Strongly-typed report DTOs and the input bundle.

Report generation is presentation only: these types are assembled from the
existing pipeline DTOs, never recomputed. The Internal Report deliberately reuses
the existing DTOs directly (they already carry the full audit trail); the Founder
Report is a human-friendly projection over the same data.

Rendering (markdown / dict / future PDF) is handled separately -- see renderers.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Mapping

from app.api.v1.reasoning.schemas import (
    BusinessHealthScore,
    CategoryRisk,
    DiagnosisResult,
    FollowUpTrigger,
    LLMClassification,
    Recommendation,
    RecommendationResult,
    RootCauseDetection,
    ScoredRootCause,
    StageDetection,
    SymptomDetection,
)
from app.services.retrieval.evidence import RetrievalEvidence


# ---------------------------------------------------------------------------
# Inputs -- profiles + the assembled pipeline bundle
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FounderProfile:
    """Founder-identity context for the report (supplied by the caller)."""

    founder_id: int
    full_name: str | None = None
    experience_level: str | None = None
    emotional_state: str | None = None


@dataclass(frozen=True)
class BusinessProfile:
    """Business context for the report (supplied by the caller)."""

    business_model: str | None = None
    industry: str | None = None
    current_revenue: str | None = None
    problem_statement: str | None = None


@dataclass(frozen=True)
class ReasoningBundle:
    """Everything the pipeline produced for a session, grouped for reporting.

    A container over existing DTOs -- it performs no computation. `*_labels` are
    optional human-readable name lookups the caller may supply (e.g. from the
    root_causes / interventions tables it already loaded); the report falls back
    to codes when they are absent, so no DB access happens here.
    """

    diagnosis: DiagnosisResult
    detections: tuple[RootCauseDetection, ...]
    scored_root_causes: tuple[ScoredRootCause, ...]
    recommendations: RecommendationResult
    overall_confidence_score: Decimal
    routing_state: str
    founder_profile: FounderProfile
    business_profile: BusinessProfile
    session_id: int | None = None
    root_cause_labels: Mapping[int, str] = field(default_factory=dict)
    intervention_labels: Mapping[int, str] = field(default_factory=dict)
    # Weighted readiness across the six pillars (readiness_pillars); optional so
    # the bundle is constructible without it.
    business_health: BusinessHealthScore | None = None


# ---------------------------------------------------------------------------
# Founder Report (projection)
# ---------------------------------------------------------------------------


class HealthBand(str, Enum):
    HEALTHY = "healthy"
    WATCH = "watch"
    AT_RISK = "at_risk"


@dataclass(frozen=True)
class CategorySnapshot:
    category: str
    risk: Decimal
    band: HealthBand
    is_flagged: bool


@dataclass(frozen=True)
class FounderStageSection:
    stage_id: int | None
    stage_name: str | None
    confidence: Decimal
    narrative: str


@dataclass(frozen=True)
class BusinessHealthSnapshot:
    overall_confidence: Decimal
    routing_state: str
    flagged_category_count: int
    categories: tuple[CategorySnapshot, ...]
    headline: str


@dataclass(frozen=True)
class RootCauseHighlight:
    root_cause_id: int
    label: str
    category: str
    rank: int
    confirmation_status: str
    confidence: Decimal
    contributing_factors: tuple[str, ...]


@dataclass(frozen=True)
class SymptomHighlight:
    category: str
    symptoms: tuple[str, ...]
    severity: Decimal
    is_distress: bool


@dataclass(frozen=True)
class PriorityAction:
    priority: int
    recommendation_type: str
    intervention_label: str
    action: str
    confidence: Decimal


@dataclass(frozen=True)
class InterventionHighlight:
    intervention_id: int
    label: str
    section: str | None
    recommendation_type: str
    next_actions: tuple[str, ...]
    supporting_root_causes: tuple[int, ...]


@dataclass(frozen=True)
class FounderReport:
    generated_for: str
    distress_acknowledged: bool
    executive_summary: str
    founder_stage: FounderStageSection
    business_health: BusinessHealthSnapshot
    top_root_causes: tuple[RootCauseHighlight, ...]
    key_symptoms: tuple[SymptomHighlight, ...]
    priority_actions: tuple[PriorityAction, ...]
    recommended_interventions: tuple[InterventionHighlight, ...]
    next_steps: tuple[str, ...]
    # Readiness pillar scores, overall health, band and triggered red flags.
    business_health_score: BusinessHealthScore | None = None


# ---------------------------------------------------------------------------
# Internal Consultant Report (curation of existing DTOs)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConfidenceBreakdown:
    overall_confidence: Decimal
    routing_state: str
    top_finding_count: int
    distress_mode: bool
    distress_signal_count: int


@dataclass(frozen=True)
class InternalReport:
    session_id: int | None
    confidence_breakdown: ConfidenceBreakdown
    # Complete scoring audit -- each carries its four-factor components.
    scoring_audit: tuple[ScoredRootCause, ...]
    category_risk_analysis: tuple[CategoryRisk, ...]
    stage_detection: StageDetection
    recommendation_rationale: tuple[Recommendation, ...]
    retrieval_evidence: tuple[RetrievalEvidence, ...]
    llm_reasoning: tuple[LLMClassification, ...]
    # Full diagnostic trace: per-cause evidence, factors, semantic hits.
    diagnostic_trace: tuple[RootCauseDetection, ...]
    follow_up_triggers: tuple[FollowUpTrigger, ...]
    symptoms: tuple[SymptomDetection, ...]
