from uuid import UUID

from fastapi import Depends, status
from sqlalchemy.orm import Session

from app.core.auth import AuthUser, get_current_founder
from app.db.session import get_db
from app.middleware.error_handler import AppError
from app.models import Founder


class FounderNotFoundError(AppError):
    """The token is valid but no founder row exists for it yet."""

    def __init__(self, message: str = "No founder profile exists for this account"):
        super().__init__(message, status_code=status.HTTP_404_NOT_FOUND)


class InvalidFounderIdentityError(AppError):
    """The token's subject is not a uuid, so it cannot match founders.user_id."""

    def __init__(self, message: str = "Token subject is not a valid founder identity"):
        super().__init__(message, status_code=status.HTTP_400_BAD_REQUEST)


def get_founder_record(
    auth_user: AuthUser = Depends(get_current_founder),
    db: Session = Depends(get_db),
) -> Founder:
    """Resolve the authenticated token to the founder row it belongs to.

    Use this instead of `get_current_founder` wherever a route touches founder
    data -- it turns the token identity into the `founder_id` the other 66
    tables join on.

    Two failure modes worth understanding:

    - 400: the token subject is not a uuid. In practice this only happens in dev
      mode, where any bearer string becomes the founder id.
    - 404: the token is valid but no founder row exists. Founder rows are
      created by the `create_founder_on_signup` database function at signup, and
      `founders.user_id` is a FK to `auth.users`, so a row cannot be conjured
      for an identity that Supabase Auth does not know about.
    """
    try:
        user_uuid = UUID(str(auth_user.id))
    except (ValueError, AttributeError, TypeError) as exc:
        raise InvalidFounderIdentityError() from exc

    founder = db.query(Founder).filter(Founder.user_id == user_uuid).first()
    if founder is None:
        raise FounderNotFoundError()

    return founder
