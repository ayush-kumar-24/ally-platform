from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# --- Account settings -------------------------------------------------------

class AccountSettingsRead(BaseModel):
    """Account-level info. Most is read-only (owned by auth/billing)."""

    model_config = ConfigDict(from_attributes=True)

    email: str
    full_name: str
    plan_type: str
    preferred_language: str | None = None
    profile_completed: bool
    created_at: datetime | None = None


class AccountSettingsUpdate(BaseModel):
    """The only account field the founder edits here. Name lives on /profile;
    email/plan are owned by auth/billing and are not editable."""

    model_config = ConfigDict(extra="forbid")

    preferred_language: str | None = Field(default=None, max_length=10)


# --- Notification preferences ----------------------------------------------

class NotificationPreferencesRead(BaseModel):
    """The known notification toggles (stored in founders.notification_preferences)."""

    model_config = ConfigDict(extra="allow")  # keep any custom keys the client stored

    in_app_all: bool = True
    email_reminders: bool = True
    email_report_ready: bool = True


class NotificationPreferencesUpdate(BaseModel):
    """Partial update -- only the toggles sent are changed; the rest are kept."""

    model_config = ConfigDict(extra="forbid")

    in_app_all: bool | None = None
    email_reminders: bool | None = None
    email_report_ready: bool | None = None


# --- Security ---------------------------------------------------------------

class SecurityRead(BaseModel):
    """Security overview. This is social-login only -- there is no password to
    manage; the identity provider (Google / LinkedIn via Supabase) owns
    credentials, password reset, and 2FA."""

    login_method: str = "social"          # Google / LinkedIn, no password
    auth_provider: str                    # active provider (dev | supabase)
    password_set: bool = False            # no passwords in this system
    managed_by: str = "identity provider (Google/LinkedIn via Supabase)"


# --- Overview ---------------------------------------------------------------

class SettingsOverview(BaseModel):
    account: AccountSettingsRead
    notifications: NotificationPreferencesRead
    security: SecurityRead
