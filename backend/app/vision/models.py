"""Vision domain models.

Backs the "Your Vision" page: six fixed territories (life/business/impact/
financial/ideal_day/legacy) the founder writes their own statement for, plus
one summary of three free-text fields (target/current/unit). Two frozen
dataclasses rather than one -- the frontend already treats them as separate
concerns (services/vision.js's `territories` map vs. its `summary` object),
and a territory is naturally keyed by (founder_id, territory) while the
summary is one row per founder.

Immutable frozen dataclasses -- same reasoning as every other domain model
in this codebase (see app/consents/models.py): the service returns these,
never ORM rows.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

# The six territories the frontend renders, in the order shown there
# (frontend/src/services/vision.js's TERRITORIES). Kept here as the single
# source of truth for what's a *valid* territory key server-side; the
# frontend's copy of this list additionally carries display label/placeholder
# text, which is presentation-only and has no reason to live in the backend.
TERRITORY_KEYS = ("life", "business", "impact", "financial", "ideal_day", "legacy")


@dataclass(frozen=True)
class VisionTerritory:
    founder_id: int
    territory: str
    statement: str
    tag1: str
    tag2: str
    updated_at: datetime


@dataclass(frozen=True)
class VisionSummary:
    founder_id: int
    target: str
    current: str
    unit: str
    updated_at: datetime
