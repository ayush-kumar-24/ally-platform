"""Plans API dependencies.

`chat_gate` enforces plan limits as a FastAPI dependency that runs *in front of*
the handler, so the frozen ChatExecutionService is never modified.

Rollout switch
--------------
Enforcement is behind `PLAN_ENFORCEMENT_ENABLED` (default **off**). This is not
timidity -- the tables the gate reads (`daily_token_usage`, `plan_call_usage`) and
the credit columns it checks do not exist in the database yet, because the
migrations are blocked. Turning the gate on before its storage exists would 500
every chat request. It ships tested and dormant; flip the flag once
`alembic upgrade head` has run.

When the flag is off the gate is a pass-through that still resolves the founder, so
turning it on changes behaviour in exactly one place rather than rewiring routes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.chat.dependencies import get_current_founder_id
from app.core.container import container
from app.db.session import get_db
from app.plans.catalog import DEFAULT_TIER, Feature
from app.plans.service import EntitlementService


def enforcement_enabled() -> bool:
    return os.environ.get("PLAN_ENFORCEMENT_ENABLED", "").strip().lower() in {"1", "true", "yes"}


def get_entitlement_service(db: Session = Depends(get_db)) -> EntitlementService:
    return container.entitlement_service(db)


def _tier_for(db: Session, founder_id: int) -> str:
    """Resolve a founder's plan. Anything unresolvable is treated as Free.

    Fails closed: an unknown founder or a missing column must grant the least,
    never the most.
    """
    try:
        tier = db.execute(text("select plan_type from founders where founder_id = :f"),
                          {"f": founder_id}).scalar()
        return tier or DEFAULT_TIER.value
    except Exception:
        db.rollback()
        return DEFAULT_TIER.value


@dataclass
class ChatGate:
    """Carries the founder, tier and service so the handler can charge after the
    model replies without a second lookup."""

    founder_id: int
    tier: str
    service: EntitlementService | None
    enforced: bool
    #: Where unbilled usage goes when metering fails. None in the dormant path.
    reconciliation: object | None = None

    def require_voice(self) -> None:
        """Call when a request carries voice input.

        Nothing calls this yet -- voice input is not implemented in chat. It exists
        so the gate is already correct the moment voice ships.
        """
        if self.enforced and self.service is not None:
            self.service.require_feature(self.tier, Feature.VOICE_CHAT)

    def record(self, tokens: int, *, is_first_diagnosis: bool = False,
               reason: str = "Ally chat", source: str = "chat") -> dict | None:
        """Charge for real usage, after the model has replied.

        On failure the user still gets their answer -- the reply exists and the
        provider tokens are already spent, so failing now would punish them for our
        accounting problem. But the shortfall is NOT swallowed: it is logged with
        structure and written to the reconciliation queue so it can be replayed and,
        until then, counted and alerted on. Silence here is revenue evaporating at
        exactly the moments the system is already unhealthy.
        """
        if not self.enforced or self.service is None:
            return None
        try:
            return self.service.record_chat_usage(
                self.founder_id, self.tier, tokens=tokens,
                is_first_diagnosis=is_first_diagnosis, reason=reason)
        except Exception as exc:                          # noqa: BLE001
            if not is_first_diagnosis:
                from app.plans.catalog import credits_for_tokens
                from app.plans.reconciliation import report_meter_failure
                report_meter_failure(
                    self.reconciliation, founder_id=self.founder_id, tokens=tokens,
                    credits_owed=credits_for_tokens(tokens), source=source, error=exc)
            return None


def chat_gate(
    founder_id: int = Depends(get_current_founder_id),
    db: Session = Depends(get_db),
) -> ChatGate:
    """Pre-flight gate. Raises 403 / 429 / 402 before the handler body runs."""
    if not enforcement_enabled():
        return ChatGate(founder_id=founder_id, tier=DEFAULT_TIER.value,
                        service=None, enforced=False)

    service = container.entitlement_service(db)
    tier = _tier_for(db, founder_id)
    # Text is assumed; a voice request must call gate.require_voice() explicitly, so
    # a missing flag can never unlock the paid voice path.
    service.check_chat_allowed(founder_id, tier)
    from app.plans.reconciliation import SqlAlchemyReconciliationRepository
    return ChatGate(founder_id=founder_id, tier=tier, service=service, enforced=True,
                    reconciliation=SqlAlchemyReconciliationRepository(db))
