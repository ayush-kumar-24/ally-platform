"""Knowledge-graph read/traversal over the seeded reference data.

The "knowledge graph" is the relational structure problems -> root_causes ->
interventions (+ per-stage weights). These are read-only walks over seeded
reference content -- no founder data, no AI. Requires authentication but not a
founder row (uses get_current_founder, not get_founder_record).

    GET /knowledge/problems              list problems
    GET /knowledge/problems/{id}         problem + its root causes + interventions
    GET /knowledge/root-causes/{id}      root cause + its problem + per-stage weights
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.auth import AuthUser, get_current_founder
from app.db.session import get_db
from app.middleware.error_handler import AppError
from app.schemas.knowledge import (
    InterventionSummary,
    ProblemDetail,
    ProblemSummary,
    RootCauseDetail,
    RootCauseSummary,
    StageWeight,
)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


class NotFoundError(AppError):
    def __init__(self, what: str):
        super().__init__(f"{what} not found", status_code=status.HTTP_404_NOT_FOUND)


@router.get("/problems", response_model=list[ProblemSummary])
async def list_problems(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: AuthUser = Depends(get_current_founder),
    db: Session = Depends(get_db),
):
    rows = db.execute(text(
        "SELECT problem_id, problem_name, description, pillar_id FROM problems "
        "ORDER BY problem_id LIMIT :limit OFFSET :offset"
    ), {"limit": limit, "offset": offset}).mappings().all()
    return [dict(r) for r in rows]


@router.get("/problems/{problem_id}", response_model=ProblemDetail)
async def get_problem(
    problem_id: int,
    _: AuthUser = Depends(get_current_founder),
    db: Session = Depends(get_db),
):
    problem = db.execute(text(
        "SELECT problem_id, problem_name, description, pillar_id FROM problems WHERE problem_id = :id"
    ), {"id": problem_id}).mappings().first()
    if problem is None:
        raise NotFoundError("Problem")

    root_causes = db.execute(text(
        "SELECT root_cause_id, root_cause_name FROM root_causes WHERE problem_id = :id ORDER BY root_cause_id"
    ), {"id": problem_id}).mappings().all()
    interventions = db.execute(text(
        "SELECT intervention_id, intervention_code, capability_domain, section "
        "FROM interventions WHERE problem_id = :id ORDER BY intervention_id"
    ), {"id": problem_id}).mappings().all()

    return ProblemDetail(
        **problem,
        root_causes=[RootCauseSummary(**r) for r in root_causes],
        interventions=[InterventionSummary(**i) for i in interventions],
    )


@router.get("/root-causes/{root_cause_id}", response_model=RootCauseDetail)
async def get_root_cause(
    root_cause_id: int,
    _: AuthUser = Depends(get_current_founder),
    db: Session = Depends(get_db),
):
    rc = db.execute(text(
        "SELECT root_cause_id, root_cause_name, problem_id FROM root_causes WHERE root_cause_id = :id"
    ), {"id": root_cause_id}).mappings().first()
    if rc is None:
        raise NotFoundError("Root cause")

    weights = db.execute(text(
        "SELECT stage_id, stage_weight FROM root_cause_weights WHERE root_cause_id = :id ORDER BY stage_id"
    ), {"id": root_cause_id}).mappings().all()

    return RootCauseDetail(**rc, stage_weights=[StageWeight(**w) for w in weights])
