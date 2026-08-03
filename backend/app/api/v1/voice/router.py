"""Voice transcription endpoint.

Transport + plan-gating only. Diagnosis voice input is available on every plan;
chat voice input requires a paid plan (VoiceUpgradeRequiredError, 403) -- the
free plan's voice allowance is diagnosis-only, by product decision.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.api.deps import get_founder_record as get_current_founder
from app.api.v1.voice.dependencies import get_transcription_provider
from app.api.v1.voice.errors import TranscriptionUnavailableError, VoiceUpgradeRequiredError
from app.api.v1.voice.schemas import TranscriptionResponse, VoiceContext
from app.api.v1.voice.validators import validate_audio
from app.models import Founder
from app.services.voice.base import TranscriptionError, TranscriptionProvider

router = APIRouter(prefix="/voice", tags=["voice"])

FREE_PLAN = "free"


@router.post("/transcribe", response_model=TranscriptionResponse, summary="Transcribe a voice recording")
def transcribe(
    context: VoiceContext = Form(...),
    file: UploadFile = File(...),
    founder: Founder = Depends(get_current_founder),
    provider: TranscriptionProvider = Depends(get_transcription_provider),
) -> TranscriptionResponse:
    if context == "chat" and founder.plan_type == FREE_PLAN:
        raise VoiceUpgradeRequiredError()

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
