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


class InvalidPlanTierError(AdminError):
    """A plan the catalog does not have. 422 rather than a silent write: a typo
    would otherwise put founders.plan_type into a value nothing in the product
    recognises, and they would read as Free everywhere while looking set."""

    def __init__(self, tier: str):
        super().__init__(f"'{tier}' is not a plan.", status_code=422)


class TeamAccountPlanLockedError(AdminError):
    """A team account's plan cannot be changed from the panel.

    Every account in TEAM_FULL_ACCESS_EMAILS is put back on Pro by
    `ensure_team_plan` on the very next request it makes (app/plans/team.py).
    Writing another tier "worked" -- the panel said "Plan changed" -- and was
    silently undone a moment later, which read as the button being broken.
    409: the request is fine; the account's state is what refuses it.
    """

    def __init__(self, email: str):
        super().__init__(
            f"{email} is a team account (TEAM_FULL_ACCESS_EMAILS), which is held "
            "at Pro on every request -- any other plan would be undone the next "
            "time it loads a page. Remove the address from that list to change "
            "its plan.",
            status_code=status.HTTP_409_CONFLICT)


class InvalidAnnouncementError(AdminError):
    def __init__(self, reason: str):
        super().__init__(f"Invalid announcement: {reason}.", status_code=422)


class InvalidSearchError(AdminError):
    def __init__(self, reason: str):
        super().__init__(f"Invalid search: {reason}.", status_code=422)


class AdminDataUnavailableError(AdminError):
    """A read the admin panel depends on failed.

    503 rather than an empty 200: these reads used to swallow the error and
    answer zero / [], so a broken query looked exactly like "no usage yet" or
    "no feedback yet" -- and got believed. The panel shows this as an error
    with a retry instead.
    """

    def __init__(self, what: str):
        super().__init__(
            f"Could not read {what} from the database. This is an error, not an "
            "empty result -- try again, and check the server log if it persists.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
