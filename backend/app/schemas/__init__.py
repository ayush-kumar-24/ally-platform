"""Pydantic request/response shapes.

One module per domain area, mirroring app/models. Schemas are the API contract;
models are the database. Keep them separate -- a column should never leak into
a response just because it exists.
"""

from app.schemas.auth import (
    AuthStatus,
    IdentityOut,
    LogoutRequest,
    RefreshRequest,
    SessionResponse,
    TokenPair,
)
from app.schemas.founder import FounderRead, FounderUpdate

__all__ = [
    "AuthStatus",
    "IdentityOut",
    "LogoutRequest",
    "RefreshRequest",
    "SessionResponse",
    "TokenPair",
    "FounderRead",
    "FounderUpdate",
]
