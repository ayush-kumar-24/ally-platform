"""Reference/catalog endpoints -- the canonical option lists for frontend pickers.

These replace the frontend's hardcoded (and mismatched) dropdown values. Every
list is backend-owned and seed-backed, so the UI only ever offers options the
engine can actually differentiate.

    GET /reference/stages            8 founder stages, grouped for the 2-tier picker
    GET /reference/industries        the 4 seeded industries
    GET /reference/business-pillars  the 6 readiness pillars (Business-DNA dims)

Auth: requires a valid token but NOT a founder row (get_current_founder), so
onboarding can populate its pickers before the founder is provisioned. The data
is non-sensitive seeded reference content.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import AuthUser, get_current_founder
from app.db.session import get_db
from app.repositories import reference_repository
from app.schemas.reference import (
    BusinessPillarOption,
    IndustryOption,
    StageGroupOption,
    StageOption,
    StagesCatalog,
)

router = APIRouter(prefix="/reference", tags=["reference"])


@router.get("/stages", response_model=StagesCatalog)
async def list_stages(
    _: AuthUser = Depends(get_current_founder),
    db: Session = Depends(get_db),
) -> StagesCatalog:
    """The 8 founder stages, both flat (ordered) and grouped by the 2-tier label."""
    rows = reference_repository.stages(db)
    stages = [
        StageOption(
            stage_id=s.stage_id,
            stage_order=s.stage_order,
            stage_name=s.stage_name,
            onboarding_label=s.onboarding_label,
        )
        for s in rows
    ]

    # Group by onboarding_label, preserving stage_order within and across groups.
    groups: list[StageGroupOption] = []
    seen: dict[str, StageGroupOption] = {}
    for opt in stages:
        key = opt.onboarding_label or "Ungrouped"
        group = seen.get(key)
        if group is None:
            group = StageGroupOption(group=key, stages=[])
            seen[key] = group
            groups.append(group)
        group.stages.append(opt)

    return StagesCatalog(groups=groups, stages=stages)


@router.get("/industries", response_model=list[IndustryOption])
async def list_industries(
    _: AuthUser = Depends(get_current_founder),
    db: Session = Depends(get_db),
) -> list[IndustryOption]:
    """The 4 seeded industries -- the only verticals the engine differentiates."""
    return [
        IndustryOption(
            industry_id=i.industry_id,
            industry_code=i.industry_code,
            industry_name=i.industry_name,
            subtitle=i.industry_subtitle,
        )
        for i in reference_repository.industries(db)
    ]


@router.get("/business-pillars", response_model=list[BusinessPillarOption])
async def list_business_pillars(
    _: AuthUser = Depends(get_current_founder),
    db: Session = Depends(get_db),
) -> list[BusinessPillarOption]:
    """The 6 readiness pillars -- the canonical Business-DNA dimensions."""
    return [
        BusinessPillarOption(
            pillar_id=p.pillar_id,
            pillar_name=p.pillar_name,
            weightage=p.pillar_weightage,
            red_flag_threshold=p.red_flag_threshold,
            what_falls_under=list(p.what_falls_under or []),
        )
        for p in reference_repository.pillars(db)
    ]
