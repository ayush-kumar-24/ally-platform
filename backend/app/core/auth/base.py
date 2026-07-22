from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from fastapi import status

from app.middleware.error_handler import AppError


class AuthError(AppError):
    """Raised when a request carries no usable identity. Always surfaces as a 401."""

    def __init__(self, message: str = "Not authenticated"):
        super().__init__(message, status_code=status.HTTP_401_UNAUTHORIZED)


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
