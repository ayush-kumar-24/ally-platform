"""Admin errors. AppError subclasses so the global handler maps them to consistent
JSON and everything fails closed."""

from fastapi import status

from app.middleware.error_handler import AppError


class AdminError(AppError):
    """Base for admin failures."""


class UnauthorizedAdminError(AdminError):
    """The caller is authenticated but is not a recognised admin. 403 (not 401):
    a valid founder who simply lacks admin access."""

    def __init__(self):
        super().__init__("Admin access is required.", status_code=status.HTTP_403_FORBIDDEN)


class AdminForbiddenError(AdminError):
    """The admin's role is insufficient for this action."""

    def __init__(self, role: str, action: str):
        super().__init__(f"Role '{role}' is not permitted to {action}.",
                         status_code=status.HTTP_403_FORBIDDEN)


class AdminFounderNotFoundError(AdminError):
    def __init__(self, founder_id: int):
        super().__init__(f"Founder {founder_id} was not found.",
                         status_code=status.HTTP_404_NOT_FOUND)


class InvalidAnnouncementError(AdminError):
    def __init__(self, reason: str):
        super().__init__(f"Invalid announcement: {reason}.", status_code=422)


class InvalidSearchError(AdminError):
    def __init__(self, reason: str):
        super().__init__(f"Invalid search: {reason}.", status_code=422)
