"""Reference/catalog response models.

Canonical, backend-owned option lists the frontend should render its pickers
from -- instead of hardcoding its own (mismatched) values. Serving these from the
DB is what stops the UI offering options the engine cannot differentiate.

Numeric DB columns are exposed as `float`, matching `schemas/knowledge.py`.
"""

from pydantic import BaseModel


class StageOption(BaseModel):
    stage_id: int
    stage_order: int
    stage_name: str
    onboarding_label: str | None = None  # 2-tier group: "Stage 0" / "Stage 0→1" / "Stage 1→10+"


class StageGroupOption(BaseModel):
    """One tier of the 2-tier stage picker: a group and the stages under it."""

    group: str
    stages: list[StageOption]


class StagesCatalog(BaseModel):
    """Both shapes the UI needs: grouped (for the 2-tier picker) and flat (ordered)."""

    groups: list[StageGroupOption]
    stages: list[StageOption]


class IndustryOption(BaseModel):
    industry_id: int
    industry_code: str
    industry_name: str
    subtitle: str | None = None


class BusinessPillarOption(BaseModel):
    """One of the 6 readiness pillars -- the canonical Business-DNA dimensions."""

    pillar_id: int
    pillar_name: str
    weightage: float
    red_flag_threshold: float | None = None
    what_falls_under: list[str] = []
