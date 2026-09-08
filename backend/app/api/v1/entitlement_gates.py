"""Router-level entitlement gates for the features that had none.

WHY THIS FILE EXISTS
`PUBLIC_LAUNCH=true` empties the Free tier, and PUBLIC-LAUNCH-CHECKLIST.md said
that "closes all of them at once rather than leaving one route open because
somebody forgot it". That was true only of features that HAD a gate. Before
this module, `require_feature` was called in five places covering ALLY_CHAT,
VOICE_CHAT, KNOWLEDGE_CHAT, PLAN_YOUR_DAY, VISION and voice-by-context --
seven of the fifteen features a plan can gate.

DIAGNOSIS, REPORTS and GOALS had no server-side check anywhere. The diagnosis
router's only mention of the subject was a comment noting it has no gate. So
flipping the launch switch would have redirected a plan-less founder to the
billing page in the UI while every one of those endpoints still answered a
direct API call -- which is precisely the "a UI gate is not an entitlement"
failure that planning/dependencies.py warns about.

WHY THE GATES LIVE TOGETHER RATHER THAN BESIDE EACH ROUTER
vision/ and planning/ each keep their own `require_*` in their own
dependencies.py, and that is right for a feature owned by one router. These
three are not: REPORTS is served by two separate routers (reports/ and
intelligence/, which reads the same report content by another door), so its
check has to be one definition or the two drift. Keeping DIAGNOSIS and GOALS
beside it means the set of "features gated at the router" is readable in one
place, which is the thing that was missing when they were forgotten.

APPLIED AT THE ROUTER, NOT PER ENDPOINT
Same reasoning as require_vision: an endpoint added later is then protected by
default rather than by its author remembering. The one router that cannot take
a blanket dependency is reports/, because two of its endpoints serve a share
token to someone who is not a founder at all -- see require_reports.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.deps import get_founder_record
from app.core.container import container
from app.db.session import get_db
from app.models import Founder
from app.plans.catalog import Feature


def _require(founder: Founder, db: Session, feature: Feature) -> None:
    container.entitlement_service(db).require_feature(founder.plan_type, feature)


def require_diagnosis(
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
) -> None:
    """The adaptive diagnosis is the Rs 199 tier's reason to exist.

    Gating it does NOT gate onboarding: the guided flow (profile, summary,
    validate, problem) runs on its own routers, and the diagnosis is opened
    only after onboarding finishes. So a founder can still complete onboarding
    and reach the plans page with no plan at all -- which is the whole point of
    sending them there.
    """
    _require(founder, db, Feature.DIAGNOSIS)


def require_reports(
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
) -> None:
    """The Clarity Report, and everything that reads its content.

    NOT applied to the whole reports router. `/reports/shared/{token}` and
    `/reports/shared/{token}/view` resolve a share token and take no founder at
    all -- they are how somebody the founder sent a link to reads the report.
    Hanging this on the router would 401 them, or worse, evaluate an
    entitlement for a founder who is not the viewer. Those two stay on the
    public router; every founder-facing endpoint carries this.

    Also applied to the intelligence router, which serves the same report
    content through /intelligence/reports/*. Gating one and not the other
    leaves the report readable by the other door.
    """
    _require(founder, db, Feature.REPORTS)


def require_goals(
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
) -> None:
    """Goals is the Rs 499 tier's near-horizon counterpart to Vision.

    vision/router.py's docstring says Goals "stays ungated" -- that described
    the testing phase, when Free carried it. Once Free is empty an ungated
    Goals router serves a founder with no plan, so the comment is corrected
    there alongside this.
    """
    _require(founder, db, Feature.GOALS)
