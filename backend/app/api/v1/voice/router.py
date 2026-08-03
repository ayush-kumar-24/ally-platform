"""Voice transcription endpoint.

Transport + plan-gating only. Gating goes through the same entitlement catalog
as every other plan-gated feature (app/plans/catalog.py): VOICE_DIAGNOSIS is
universal (free plan included), VOICE_CHAT is paid-only. That catalog is the
one place tier/feature rules are declared -- this endpoint doesn't decide
"free plan" itself, it just asks the catalog, same as chat_gate/PlanGate do.
`require_feature` (unlike chat_gate's usage/credit checks) is pure catalog
lookup with no DB usage table involved, so this works regardless of whether
PLAN_ENFORCEMENT_ENABLED (the token-metering rollout switch) is on.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_founder_record as get_current_founder
from app.api.v1.voice.dependencies import get_transcription_provider
from app.api.v1.voice.errors import TranscriptionUnavailableError
from app.api.v1.voice.schemas import TranscriptionResponse, VoiceContext
from app.api.v1.voice.validators import validate_audio
from app.core.container import container
from app.db.session import get_db
from app.models import Founder
from app.plans.catalog import Feature
from app.services.voice.base import TranscriptionError, TranscriptionProvider

router = APIRouter(prefix="/voice", tags=["voice"])

_FEATURE_FOR_CONTEXT = {"chat": Feature.VOICE_CHAT, "diagnosis": Feature.VOICE_DIAGNOSIS}


@router.post("/transcribe", response_model=TranscriptionResponse, summary="Transcribe a voice recording")
def transcribe(
    context: VoiceContext = Form(...),
    file: UploadFile = File(...),
    founder: Founder = Depends(get_current_founder),
    provider: TranscriptionProvider = Depends(get_transcription_provider),
    db: Session = Depends(get_db),
) -> TranscriptionResponse:
    entitlements = container.entitlement_service(db)
    entitlements.require_feature(founder.plan_type, _FEATURE_FOR_CONTEXT[context])

    content = file.file.read()
    validate_audio(content)

    try:
        text = provider.transcribe(
            content, filename=file.filename or "recording.webm",
            content_type=file.content_type or "audio/webm",
        )
    except TranscriptionError as exc:
        raise TranscriptionUnavailableError(str(exc)) from exc

    return TranscriptionResponse(text=text)
