"""Compatibility aliases for the reasoning call sites -- see models/diagnosis.py.

Re-exports the canonical `schema.py` tables under the singular names the reasoning
engine imports. No tables are defined here.
"""

from app.models.schema import (
    AgentInterpretations as AgentInterpretation,
    DetectedRootCauses as DetectedRootCause,
    FounderReports as FounderReport,
    Industries as Industry,
    InternalIntelligenceReports as InternalIntelligenceReport,
    Interventions as Intervention,
    ProblemStageMapping,
    Problems as Problem,
    RootCauses as RootCause,
    RootCauseWeights as RootCauseWeight,
    StageAssessments as StageAssessment,
    StageDiagnosisLogic,
)

__all__ = [
    "AgentInterpretation",
    "DetectedRootCause",
    "FounderReport",
    "Industry",
    "InternalIntelligenceReport",
    "Intervention",
    "Problem",
    "ProblemStageMapping",
    "RootCause",
    "RootCauseWeight",
    "StageAssessment",
    "StageDiagnosisLogic",
]
