"""Errors for the Ally prompt layer. No generic exceptions escape this package.

Every failure mode named in the milestone maps to a dedicated, typed error so the
Prompt Manager can fail closed with a precise reason instead of a silent default.
"""

from fastapi import status

from app.middleware.error_handler import AppError


class PromptError(AppError):
    """Base for all prompt-layer errors."""


class PromptNotFoundError(PromptError):
    """No template matches the requested selection (category / stage / distress /
    language / variant). A configuration gap, not a client error -> 500."""

    def __init__(self, detail: str):
        super().__init__(
            f"No prompt template found for {detail}.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class TemplateVersionError(PromptError):
    """A specific template version was requested but does not exist."""

    def __init__(self, category: str, requested: int, available: list[int]):
        super().__init__(
            f"Prompt '{category}' has no version {requested}; available: {available}.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class MissingPromptVariableError(PromptError):
    """A required variable was absent from the context, or a placeholder referenced
    a variable that was not supplied. Fail closed -- never substitute a default."""

    def __init__(self, template_key: str, missing: list[str]):
        super().__init__(
            f"Prompt '{template_key}' is missing required variable(s): {missing}.",
            # 422 as a literal: the named Starlette constant was renamed
            # (UNPROCESSABLE_ENTITY -> UNPROCESSABLE_CONTENT); the number is stable.
            status_code=422,
        )


class UnsupportedLanguageError(PromptError):
    """The requested language is not supported by this manager. Distinct from
    'no template in that language' -- this rejects the request up front."""

    def __init__(self, language: str, supported: list[str]):
        super().__init__(
            f"Language '{language}' is not supported; supported: {supported}.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class RenderingError(PromptError):
    """The template could not be rendered for a reason other than a missing
    variable (e.g. a malformed template body)."""

    def __init__(self, template_key: str, reason: str):
        super().__init__(
            f"Prompt '{template_key}' failed to render: {reason}.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
