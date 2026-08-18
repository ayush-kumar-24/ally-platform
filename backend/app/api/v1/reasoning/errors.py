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


class NoClassifiableAnswersError(ReasoningError):
    """The session has answers, but not one of them could be classified -- so the
    pipeline has zero evidence to reason from.

    This is its own error because of what used to happen instead. Individual
    unscored answers are skipped rather than failing the batch (see
    StandardDiagnosticEngine.classify_answers), which is right for one bad row and
    catastrophic for all of them: when EVERY answer is unscored the pipeline runs
    happily to completion on an empty classification set, detects no root causes,
    scores no confidence, and persists a founder_report containing nothing. No
    exception, no error log, a 200 response, and a founder who answered thirty
    questions reading a report with no findings in it.

    That state is reachable purely from configuration -- ADAPTIVE_QUESTIONS=false
    (so the submit-time advisor never writes answers.score_label) plus
    ANSWER_CLASSIFIER=stored (so the pipeline only reads it), which is exactly the
    pair backend/.env.example ships and DEPLOY_AWS.md's env table does not
    mention. Two independent flags silently decided whether the product's core
    output contained anything.

    Failing here is deliberately the harsher option, and it follows the rule the
    frontend already states in services/reports.js: a fabricated profile that
    reads as real is worse than an empty state, because the founder acts on it.
    A rolled-back pipeline leaves the session recoverable -- the reconciliation
    sweep retries it, and reasoning is idempotent -- whereas a persisted empty
    report is indistinguishable from a real one and satisfies the
    already-has-a-report guard forever.
    """

    def __init__(self, message: str = "No answer in this session could be classified."):
        # Literal 422, matching DiagnosisDataError above -- the named constant is
        # deprecated in this Starlette version and warns on every construction.
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
