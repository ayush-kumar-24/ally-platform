from uuid import UUID

from fastapi import Depends, status
from sqlalchemy.orm import Session

from app.core.auth import AuthUser, get_current_founder
from app.db.session import get_db, set_founder_rls_context
from app.middleware.error_handler import AppError
from app.models import Founder
from app.repositories import founder_repository
from app.services.profile_progress import validate_profile


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

    set_founder_rls_context(db, str(user_uuid))

    founder = founder_repository.get_by_user_id(db, user_uuid)
    if founder is None:
        raise FounderNotFoundError()

    return founder


class ProfileIncompleteError(AppError):
    """Onboarding is not finished, so the journey cannot start.

    Onboarding is where Ally learns who someone is -- their stage, what they
    are building, their revenue, the problem they arrived with. Every phase
    after it consumes that: stage selects which question bank the diagnosis
    draws from, and the rest is the founder context the advisor reads before
    choosing each question (see diagnosis/founder_brief.py).

    Starting without it does not produce a slightly worse diagnosis, it
    produces a different one -- generic questions with no stage and no
    situation behind them. Refusing is the honest outcome, and it is
    recoverable in one place: finish the profile.

    Carries `missing` so the client can send the founder straight to the
    fields that are actually blocking them rather than to the top of a form
    they mostly filled in already.
    """

    def __init__(self, missing: list[dict] | None = None):
        fields = missing or []
        names = ", ".join(str(m.get("label") or m.get("field")) for m in fields[:4])
        detail = f" Still needed: {names}." if names else ""
        super().__init__(
            "Finish setting up your profile before starting -- Ally uses it to "
            "choose the right questions for you." + detail,
            status_code=status.HTTP_409_CONFLICT,
        )
        self.missing = fields


def require_profile_complete(
    founder: Founder = Depends(get_founder_record),
) -> Founder:
    """Refuse the request until onboarding is done.

    Recomputes completeness rather than reading `founders.profile_completed`.
    The column is kept truthful on every profile write (see
    FounderRepository.update), but it is a cache, and a founder whose required
    fields changed by any other route -- an admin edit, a data import, a new
    required field added to onboarding -- would otherwise be let through on a
    stale true. The check is a handful of attribute reads on a row already
    loaded, so there is no reason to trust the cache over the source.
    """
    result = validate_profile(founder)
    if not result["valid"]:
        raise ProfileIncompleteError(result["missing"])
    return founder
