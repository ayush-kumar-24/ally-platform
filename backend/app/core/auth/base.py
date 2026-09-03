from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from fastapi import status

from app.middleware.error_handler import AppError


class AuthError(AppError):
    """Raised when a request carries no usable identity. Always surfaces as a 401."""

    def __init__(self, message: str = "Not authenticated"):
        super().__init__(message, status_code=status.HTTP_401_UNAUTHORIZED)


class AccountSuspendedError(AppError):
    """Raised when a cryptographically valid token belongs to a founder whose
    account is currently suspended or banned.

    Deliberately 403, not 401: the token itself is fine (AuthError is the
    "who are you" failure) -- this is "we know who you are, and you are not
    allowed in right now". Distinguishing the two matters to a client: a 401
    means "log in again", a 403 here means "this won't fix itself with a new
    token", which is the truth for a suspended account.
    """

    def __init__(self, message: str = "This account no longer has access"):
        super().__init__(message, status_code=status.HTTP_403_FORBIDDEN)


@dataclass(frozen=True)
class AuthUser:
    """The identity behind a request, normalised across auth providers.

    `id` is the founder id used everywhere downstream -- it is whatever the
    provider considers the stable subject of the token (Supabase's `sub`).
    """

    id: str
    email: str | None = None
    provider: str = "unknown"
    claims: dict[str, Any] = field(default_factory=dict)


class AuthProvider(ABC):
    """Contract every auth backend implements.

    Swapping Supabase for Cognito later means adding one subclass and changing
    AUTH_PROVIDER -- no route or service code changes.
    """

    name: str = "base"

    @abstractmethod
    def verify_token(self, token: str | None) -> AuthUser:
        """Return the AuthUser for this token, or raise AuthError."""
        raise NotImplementedError
