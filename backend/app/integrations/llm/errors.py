"""Errors raised by the real LLM provider adapters.

These are plain exceptions (not AppError): the frozen AIExecutionService catches
provider exceptions and fails closed to an empty AIResponse, and treats a builtin
TimeoutError specially (records `timed_out`). So a timeout is raised as
TimeoutError; every other provider failure is one of these, which the service
records as a retriable provider error.
"""


class LLMProviderCallError(Exception):
    """Base for a failed provider call."""


class LLMRateLimitError(LLMProviderCallError):
    """HTTP 429 -- the provider rate-limited the request."""


class LLMAuthError(LLMProviderCallError):
    """HTTP 401/403 -- bad or missing API key."""


class LLMUnavailableError(LLMProviderCallError):
    """HTTP 5xx or a transport/connection error -- provider unavailable."""
