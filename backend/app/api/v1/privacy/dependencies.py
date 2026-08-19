"""Privacy Center API dependencies. Tests override both."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.deps import get_founder_record
from app.api.v1.plans.dependencies import get_current_founder_id as _plans_get_current_founder_id
from app.core.container import container
from app.db.session import get_db
from app.models import Founder
from app.privacy.errors import ProcessingRestrictedError
from app.privacy.service import PrivacyService


def get_current_founder_id(founder: Founder = Depends(get_founder_record)) -> int:
    return founder.founder_id


def get_privacy_service(db: Session = Depends(get_db)) -> PrivacyService:
    return container.privacy_service(db)


def require_ai_processing_allowed(
    founder: Founder = Depends(get_founder_record),
    privacy: PrivacyService = Depends(get_privacy_service),
) -> None:
    """Gate for every route that actually calls an LLM on the founder's behalf
    (diagnosis start/answer, founder-dna start/answer, chat message/stream).

    Without this, "Restrict data processing" / "Withdraw consent" in the
    Privacy Center saved a flag nobody read -- the diagnosis engine, Founder
    DNA engine and chat kept generating AI output regardless. This is what
    makes that flag real: add `Depends(require_ai_processing_allowed)` to any
    route that starts or advances an AI-processed flow.

    Deliberately does NOT gate read-only routes (GET /diagnosis/current,
    GET /founder-dna/current, listing conversations, etc.) -- those only
    serve state that already exists, no new processing happens.
    """
    if not privacy.may_process(founder.founder_id):
        raise ProcessingRestrictedError(founder.founder_id)


def require_ai_processing_allowed_for_id(
    # Deliberately the SAME callable chat's own ChatGate resolves founder_id
    # with (app.api.v1.plans.dependencies.get_current_founder_id, re-exported
    # through app.api.v1.chat.dependencies) rather than this module's own
    # get_current_founder_id above. FastAPI's dependency_overrides key on the
    # exact callable object -- tests override the plans one (that's what
    # ChatGate itself depends on), so this must depend on the same object or
    # it would bypass the override and hit a real DB the offline chat tests
    # never configure.
    founder_id: int = Depends(_plans_get_current_founder_id),
    privacy: PrivacyService = Depends(get_privacy_service),
) -> None:
    """Same gate as require_ai_processing_allowed, for routes (chat's
    /message and /stream) that only resolve a founder_id via their own gate
    dependency (ChatGate), not a Founder object."""
    if not privacy.may_process(founder_id):
        raise ProcessingRestrictedError(founder_id)
