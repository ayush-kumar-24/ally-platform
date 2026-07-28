"""Errors for the M2.1 grounding layer. Extends the frozen prompt-layer error tree
so grounded rendering fails closed with a precise, typed reason."""

from fastapi import status

from app.api.v1.ally.prompts.errors import PromptError


class GroundingError(PromptError):
    """A grounded prompt could not be assembled -- e.g. no AllyContext to ground in.
    A configuration/wiring gap, not a client error -> 500."""

    def __init__(self, template_key: str, reason: str):
        super().__init__(
            f"Grounded prompt '{template_key}' could not be built: {reason}.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
