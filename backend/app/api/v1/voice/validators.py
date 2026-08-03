from __future__ import annotations

from app.api.v1.voice.errors import AudioTooLargeError, InvalidAudioError

# Voice notes, not file uploads -- a few minutes of compressed audio (webm/opus,
# mp4/aac) is a few MB at most. Well under the 25 MiB attachment cap on purpose:
# a different domain (attachments/validators.py), not reused here.
MAX_AUDIO_SIZE_BYTES = 15 * 1024 * 1024


def validate_audio(content: bytes) -> None:
    if not content:
        raise InvalidAudioError("recording is empty")
    if len(content) > MAX_AUDIO_SIZE_BYTES:
        raise AudioTooLargeError(len(content), MAX_AUDIO_SIZE_BYTES)
