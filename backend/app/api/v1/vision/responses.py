"""Vision API response models with `from_domain` mappers."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.vision.models import TERRITORY_KEYS, VisionSummary, VisionTerritory


class VisionTerritoryResponse(BaseModel):
    territory: str
    statement: str
    tag1: str
    tag2: str
    updated_at: datetime | None

    @classmethod
    def from_domain(cls, territory_key: str, t: VisionTerritory | None) -> "VisionTerritoryResponse":
        """t is None when the founder hasn't written this territory yet --
        rendered as empty fields, never a fabricated statement."""
        if t is None:
            return cls(territory=territory_key, statement="", tag1="", tag2="", updated_at=None)
        return cls(territory=t.territory, statement=t.statement, tag1=t.tag1, tag2=t.tag2, updated_at=t.updated_at)


class VisionSummaryResponse(BaseModel):
    target: str
    current: str
    unit: str
    updated_at: datetime | None

    @classmethod
    def from_domain(cls, s: VisionSummary | None) -> "VisionSummaryResponse":
        if s is None:
            return cls(target="", current="", unit="", updated_at=None)
        return cls(target=s.target, current=s.current, unit=s.unit, updated_at=s.updated_at)


class VisionResponse(BaseModel):
    """The full GET /vision snapshot -- same {territories, summary} shape
    the frontend already builds client-side in services/vision.js's
    emptyVision(), so no frontend reshaping is needed."""
    territories: dict[str, VisionTerritoryResponse]
    summary: VisionSummaryResponse

    @classmethod
    def from_domain(
        cls, territories: dict[str, VisionTerritory | None], summary: VisionSummary | None,
    ) -> "VisionResponse":
        return cls(
            territories={key: VisionTerritoryResponse.from_domain(key, territories.get(key)) for key in TERRITORY_KEYS},
            summary=VisionSummaryResponse.from_domain(summary),
        )
