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


class AccountPendingApprovalError(AppError):
    """Signed in successfully, but the account has not been approved yet.

    403 and not 401: the token is perfectly valid and re-authenticating changes
    nothing, so the frontend must not treat this as a session problem and try to
    refresh. It is a state only a human on our side can move.
    """

    def __init__(self, message: str = (
        "Your account is awaiting approval. We'll email you as soon as it's ready."
    )):
        super().__init__(message, status_code=status.HTTP_403_FORBIDDEN)


class AccountNotActiveError(AppError):
    """Suspended, banned or deactivated -- signed in, but not permitted.

    Deliberately one error for all three rather than three that name the state:
    a banned account learning it is banned rather than merely inactive gains
    nothing legitimate and tells someone probing exactly where they stand. The
    admin panel and the audit log carry the real reason.
    """

    def __init__(self, message: str = (
        "This account is not currently active. Contact info@goxl.in if you think "
        "this is a mistake."
    )):
        super().__init__(message, status_code=status.HTTP_403_FORBIDDEN)


#: The only status permitted to use the product. Everything else -- 'pending'
#: awaiting approval, and the three the admin panel can set -- is refused by
#: `get_founder_record` below.
ACTIVE_STATUS = "active"


def assert_account_usable(founder: Founder) -> None:
    """Refuse a founder whose account is not active.

    This is the enforcement half of a column that had none. `founders.status`
    has existed since the admin panel shipped, with an endpoint to set it and an
    audit trail behind it, but nothing outside that panel ever read it -- so
    "suspend" and "ban" wrote a string and the founder carried on with full
    access. Everything authenticated resolves through `get_founder_record`, so
    checking here covers the whole API rather than the routes someone remembered.

    A missing or NULL status reads as active on purpose. The column is nullable
    in some environments (see users_db_repository's optional-column handling),
    and failing closed on absence would lock out every founder the moment this
    deploys somewhere the column was never backfilled.
    """
    current = (getattr(founder, "status", None) or ACTIVE_STATUS)
    if current == ACTIVE_STATUS:
        return
    if current == "pending":
        raise AccountPendingApprovalError()
    raise AccountNotActiveError()


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
    - 403: the row exists and the token is fine, but the account is not active --
      awaiting approval, or suspended/banned by an admin. See
      `assert_account_usable`.
    """
    try:
        user_uuid = UUID(str(auth_user.id))
    except (ValueError, AttributeError, TypeError) as exc:
        raise InvalidFounderIdentityError() from exc

    set_founder_rls_context(db, str(user_uuid))

    founder = founder_repository.get_by_user_id(db, user_uuid)
    if founder is None:
        raise FounderNotFoundError()

    # Every authenticated route in the API resolves through here, so this is the
    # one place that has to ask whether the account is allowed to be used at all.
    assert_account_usable(founder)

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
