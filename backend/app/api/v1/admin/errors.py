"""Admin API error surface. Domain errors are AppError subclasses mapped by the
global handler (403 unauthorized/forbidden, 404 not found, 422 invalid input)."""

from app.admin.errors import (
    AdminError,
    AdminForbiddenError,
    AdminFounderNotFoundError,
    InvalidAnnouncementError,
    InvalidSearchError,
    UnauthorizedAdminError,
)

__all__ = [
    "AdminError", "UnauthorizedAdminError", "AdminForbiddenError",
    "AdminFounderNotFoundError", "InvalidAnnouncementError", "InvalidSearchError",
]
