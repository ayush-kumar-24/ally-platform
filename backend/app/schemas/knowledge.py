from pydantic import BaseModel


class ProblemSummary(BaseModel):
    problem_id: int
    problem_name: str
    description: str | None = None
    pillar_id: int | None = None


class RootCauseSummary(BaseModel):
    root_cause_id: int
    root_cause_name: str


class InterventionSummary(BaseModel):
    intervention_id: int
    intervention_code: str | None = None
    capability_domain: str | None = None
    section: str | None = None


class StageWeight(BaseModel):
    stage_id: int
    stage_weight: float | None = None


class ProblemDetail(ProblemSummary):
    """A problem plus the graph one hop out: its root causes and interventions."""

    root_causes: list[RootCauseSummary]
    interventions: list[InterventionSummary]


class RootCauseDetail(RootCauseSummary):
    """A root cause plus its problem and its per-stage weights."""

    problem_id: int | None = None
    stage_weights: list[StageWeight]
