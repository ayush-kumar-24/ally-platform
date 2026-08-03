from fastapi import status

from app.middleware.error_handler import AppError


class VoiceError(AppError):
    """Base for all voice-transcription errors."""


class VoiceUpgradeRequiredError(VoiceError):
    """Voice input in chat is a paid-plan feature; diagnosis remains free.

    The frontend keys off `error` (the class name) rather than the message
    text, so it can show its own upgrade popup instead of a generic failure.
    """

    def __init__(self) -> None:
        super().__init__(
            "Voice input in chat requires a paid plan. Voice is available on the "
            "free plan during your diagnosis.",
            status_code=status.HTTP_403_FORBIDDEN,
        )


class InvalidAudioError(VoiceError):
    def __init__(self, reason: str) -> None:
        super().__init__(f"Invalid audio: {reason}.", status_code=422)


class AudioTooLargeError(VoiceError):
    def __init__(self, size: int, max_size: int) -> None:
        super().__init__(
            f"Audio is {size} bytes; the limit is {max_size} bytes.",
            status_code=413,
        )


class TranscriptionUnavailableError(VoiceError):
    def __init__(self, detail: str) -> None:
        super().__init__(
            f"Voice transcription is temporarily unavailable: {detail}",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
