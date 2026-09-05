"""Plans API dependencies.

`chat_gate` enforces plan limits as a FastAPI dependency that runs *in front of*
the handler, so the frozen ChatExecutionService is never modified.

Rollout switch
--------------
Enforcement is behind `PLAN_ENFORCEMENT_ENABLED`. It was dormant because the
storage it reads did not exist; that is no longer true. `daily_token_usage`
(now carrying a `source` so chat and planning meter separately),
`plan_call_usage` and the credit columns are all migrated as of b8e2d4f60a19,
and signup credits are granted as of a7c3f9e21d84 -- without which enabling this
would have refused every newly-provisioned founder on their first message.

When the flag is off the gate is a pass-through that still resolves the founder, so
turning it on changes behaviour in exactly one place rather than rewiring routes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_founder_record
from app.core.config import settings
from app.core.container import container
from app.db.session import get_db
from app.models import Founder
from app.plans.catalog import DEFAULT_TIER, Feature
from app.plans.service import EntitlementService


def get_current_founder_id(founder: Founder = Depends(get_founder_record)) -> int:
    """The authenticated founder's id. Defined here (not in
    app.api.v1.chat.dependencies, which re-exports this same function) because
    chat.router imports ChatGate/chat_gate FROM this module -- the reverse
    direction closes a cycle through app.api.v1.chat's own __init__.py. A fresh
    process following router.py's own import order hits that immediately: it
    silently leaves plans_router with zero routes registered rather than
    raising, so every test can still pass (they import chat's package earlier
    for unrelated reasons, masking the cycle) while /plans/* stays completely
    unreachable in a real run. Single source of truth here also means chat's
    test overrides of this dependency correctly reach chat_gate too -- FastAPI
    keys dependency_overrides by function identity, so two separate copies of
    this function would silently diverge under override."""
    return founder.founder_id


def enforcement_enabled() -> bool:
    """Is the quota gate live?

    Reads the process environment FIRST so a deploy or a test can override, then
    falls back to settings (which is what loads .env). Checking only os.environ --
    as this did -- meant the flag was unsettable by the one mechanism every other
    option in this codebase uses: pydantic-settings parses .env into the Settings
    object and never exports it to the environment, so PLAN_ENFORCEMENT_ENABLED=true
    in .env was read as absent and enforcement stayed silently off.
    """
    raw = os.environ.get("PLAN_ENFORCEMENT_ENABLED")
    if raw is not None:
        return raw.strip().lower() in {"1", "true", "yes"}
    return settings.PLAN_ENFORCEMENT_ENABLED


def get_entitlement_service(db: Session = Depends(get_db)) -> EntitlementService:
    return container.entitlement_service(db)


def _plan_context(db: Session, founder_id: int) -> tuple[str, object | None]:
    """Resolve a founder's plan and trial expiry in one read.

    Fails closed on the tier: an unknown founder or a missing column must grant
    the least, never the most. The expiry degrades to None instead, which only
    costs a less specific 402 message -- never access.

    Both come from the same row deliberately: fetching the date separately would
    double the queries on the hot path for one string in an error message.
    """
    try:
        row = db.execute(
            text("select plan_type, credits_expires_at from founders where founder_id = :f"),
            {"f": founder_id}).first()
        if row is None:
            return DEFAULT_TIER.value, None
        return (row[0] or DEFAULT_TIER.value), row[1]
    except Exception:
        db.rollback()
        return DEFAULT_TIER.value, None


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

    @property
    def knowledge_enabled(self) -> bool:
        """May Ally reason over the knowledge base for this founder (Rs 999)?

        Unlike require_voice this is NOT behind `enforced`: it grants a capability
        rather than refusing a request, so leaving it dark when the quota gate is
        off would hand every founder the Rs 999 entitlement. With no service
        wired it falls back to True, which keeps the dormant/testing path behaving
        exactly as it did before plans existed.
        """
        if self.service is None:
            return True
        return self.service.has_feature(self.tier, Feature.KNOWLEDGE_CHAT)

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
    tier, trial_expires_at = _plan_context(db, founder_id)
    # Text is assumed; a voice request must call gate.require_voice() explicitly, so
    # a missing flag can never unlock the paid voice path.
    service.check_chat_allowed(founder_id, tier, trial_expires_at=trial_expires_at)
    from app.plans.reconciliation import SqlAlchemyReconciliationRepository
    return ChatGate(founder_id=founder_id, tier=tier, service=service, enforced=True,
                    reconciliation=SqlAlchemyReconciliationRepository(db))
