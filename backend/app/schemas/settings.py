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
    """The known notification toggles (stored in founders.notification_preferences).

    reduced_motion lives here too rather than on a new table: live-reported bug
    was ALL FOUR profile-page toggles being local React state only -- no backend
    call, not even localStorage, so every one reset to its default on reload.
    This is the one JSONB column on `founders` that already existed for exactly
    this shape of thing (a small set of named booleans), and `extra="allow"`
    below already tolerated unknown keys before this change, so widening it here
    needed no migration.

    REMOVED 2026-09-05: `private_mode`. Its switch was labelled "Keep business
    data anonymised in aggregate insights", which told a founder two things --
    that their business data goes into aggregate insights by default, and that
    this switch anonymises it. Neither was true. Nothing anywhere read the flag,
    and there are no aggregate insights in the product. A privacy control that
    does nothing is worse than no control, and a description of a data use we do
    not have is worse again, so it is gone rather than reworded.

    `extra="allow"` means the key already stored on existing founder rows is
    simply carried through and ignored. No migration, and nothing to clean up
    unless someone wants the rows tidy.
    """

    model_config = ConfigDict(extra="allow")  # keep any custom keys the client stored

    in_app_all: bool = True
    email_reminders: bool = True
    # Task reminders get their OWN flag rather than reusing `email_reminders`.
    # That one is read only by discovery_notifications, gating the reminder for
    # a call the founder paid for -- which is why its switch is labelled "Call
    # reminders by email". Sharing it would mean silencing task nags also
    # silences the reminder for a paid call: the exact conflation that was
    # fixed when the switch was relabelled.
    email_task_reminders: bool = True
    # The master switch for the notification fan-out: every bell item that is
    # emailed is gated on this. Separate from the two above because they are
    # different promises -- a founder may want the reminder for a call they paid
    # for while wanting nothing else in their inbox.
    email_notifications: bool = True
    email_report_ready: bool = True
    reduced_motion: bool = False


class NotificationPreferencesUpdate(BaseModel):
    """Partial update -- only the toggles sent are changed; the rest are kept."""

    model_config = ConfigDict(extra="forbid")

    in_app_all: bool | None = None
    email_reminders: bool | None = None
    email_task_reminders: bool | None = None
    email_notifications: bool | None = None
    email_report_ready: bool | None = None
    reduced_motion: bool | None = None
    # private_mode removed -- see NotificationPreferencesRead. `extra="forbid"`
    # means a client still sending it now gets a 422 rather than silently
    # writing a flag nothing reads; the only client that ever sent it was the
    # profile switch, removed in the same change.


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
