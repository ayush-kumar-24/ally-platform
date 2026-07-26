"""Domain errors for the reasoning layer.

All subclass AppError so the exception handler registered in main.py renders them
with the right status code and no per-route try/except is needed.
"""

from fastapi import status

from app.middleware.error_handler import AppError


class ReasoningError(AppError):
    """Base for reasoning-layer domain errors."""


class SessionNotAnalyzableError(ReasoningError):
    """The session exists but is not in a state that can be analysed (e.g. it is
    not completed, or has no scored answers)."""

    def __init__(self, message: str = "This session cannot be analysed yet."):
        super().__init__(message, status_code=status.HTTP_409_CONFLICT)


class DiagnosisDataError(ReasoningError):
    """An answer cannot be classified deterministically because it has no stored
    score or score_label (scoring is populated at answer time; the deterministic
    Diagnosis Engine reads it, it does not invent it)."""

    def __init__(self, message: str = "Answer has no stored score to classify."):
        super().__init__(message, status_code=422)


class FeatureDisabledError(ReasoningError):
    """A required business rule is not yet implemented, so the feature that
    depends on it is disabled rather than falling back to placeholder logic."""

    def __init__(self, message: str = "This feature is not yet available."):
        super().__init__(message, status_code=501)


class LLMClassificationError(ReasoningError):
    """The LLM classifier could not produce a valid classification after retries,
    and no deterministic fallback could be applied."""

    def __init__(self, message: str = "LLM answer classification failed."):
        super().__init__(message, status_code=502)


class ReasoningConfigError(ReasoningError):
    """The reasoning configuration is missing or invalid (bad scoring_rules,
    unconfigured strategy, weights that do not sum to 1.0)."""

    def __init__(self, message: str = "Reasoning configuration is invalid."):
        super().__init__(message, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ReasoningPersistenceError(ReasoningError):
    """A database error occurred while persisting reasoning output."""

    def __init__(self, message: str = "Could not persist reasoning results."):
        super().__init__(message, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EngineNotImplementedError(ReasoningError):
    """A pipeline engine has not been implemented yet. Distinct from Python's
    NotImplementedError so the API surfaces a clean 501 during incremental
    rollout instead of a 500."""

    def __init__(self, message: str = "This reasoning engine is not implemented yet."):
        super().__init__(message, status_code=status.HTTP_501_NOT_IMPLEMENTED)
