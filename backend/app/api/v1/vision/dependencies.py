"""Vision API dependencies."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.deps import get_founder_record
from app.core.container import container
from app.db.session import get_db
from app.models import Founder
from app.plans.catalog import Feature
from app.vision.service import VisionService


def get_current_founder_id(founder: Founder = Depends(get_founder_record)) -> int:
    return founder.founder_id


def get_vision_service(db: Session = Depends(get_db)) -> VisionService:
    return container.vision_service(db)


def require_vision(
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
) -> None:
    """Vision is a Rs 999 feature. Rs 199 and Rs 450 get Goals and daily plans
    instead -- the near horizon, not the long one.

    Applied once at the router rather than per endpoint, for the same reason
    planning does it (see require_plan_your_day): a route added later is then
    protected by default instead of by the author remembering. Note the image
    routes this covers -- an ungated PUT would let an off-plan founder write
    territories they cannot read back, which is worse than refusing them.
    """
    container.entitlement_service(db).require_feature(
        founder.plan_type, Feature.VISION
    )
