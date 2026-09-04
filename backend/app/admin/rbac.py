"""Role-based access control for the Admin Panel.

Three roles, one explicit capability matrix. Authorization is decided *here* and
enforced in the endpoint dependency -- never in the frontend. The UI hiding a button
is a usability nicety; the only thing that actually stops an action is this module.

Why a matrix instead of rank comparison: the existing Phase 12 roles were a simple
ladder (read_only < operator < admin), which works when every permission nests. The
requested roles do NOT nest cleanly -- Support may view chats while Admin's listed
duties don't mention it, and only Super Admin may touch credits regardless of how
"senior" another role looks. An explicit matrix states each answer rather than
inferring it from an ordering that doesn't hold.

Fails closed twice over: an unknown role has no capability set, and an unknown
capability is not granted to anybody.
"""

from __future__ import annotations

from enum import Enum

from app.admin.errors import AdminForbiddenError


class PanelRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    SUPPORT = "support"


class Capability(str, Enum):
    # --- read -----------------------------------------------------------
    VIEW_USERS = "view_users"
    VIEW_REPORTS = "view_reports"
    VIEW_CHATS = "view_chats"
    VIEW_AUDIT = "view_audit"
    VIEW_FEEDBACK = "view_feedback"
    # Read-only view of the growth layer: who is on the beta waitlist, which
    # cohorts have gone out, what coupons exist and how often they have been
    # claimed. Reading it tells you nothing a founder could be harmed by, so it
    # sits at the same tier as the other read capabilities.
    VIEW_GROWTH = "view_growth"
    # --- admin-level mutations ------------------------------------------
    EDIT_USER_PROFILE = "edit_user_profile"
    RESET_DIAGNOSIS = "reset_diagnosis"
    RESET_CONVERSATIONS = "reset_conversations"
    # Recovery, not destruction -- same admin tier as the other "undo" actions
    # above, not the super-admin-only DELETE_USER below. A founder whose
    # Supabase identity was deleted by mistake (or a compromised account) has
    # no way to log back in and cancel their own pending erasure; this is the
    # only path back for them, so it deliberately is NOT locked behind the
    # same tier as actions that destroy data.
    CANCEL_DELETION = "cancel_deletion"
    # DSAR fulfilment ("View data summary", "Request data correction", etc. from
    # the Privacy Center) -- same admin tier as CANCEL_DELETION: it resolves a
    # founder-initiated data-rights request, not routine account admin.
    MANAGE_PRIVACY_REQUESTS = "manage_privacy_requests"
    # --- super-admin-only mutations -------------------------------------
    TRANSFER_CREDITS = "transfer_credits"
    MODIFY_SUBSCRIPTION = "modify_subscription"
    SUSPEND_USER = "suspend_user"
    DELETE_USER = "delete_user"
    CHANGE_USER_ROLE = "change_user_role"
    SYSTEM_SETTINGS = "system_settings"
    # Creating and retiring coupons is changing what people are charged, which is
    # the same class of decision as MODIFY_SUBSCRIPTION -- Super Admin only.
    MANAGE_COUPONS = "manage_coupons"
    # Releasing a beta cohort mails every founder on the waitlist at once and is
    # not undoable once the mail is out. Blast radius, not seniority, is what puts
    # it here: an Admin who can reset one founder's diagnosis still should not be
    # one mis-click from 200 emails.
    MANAGE_BETA_ACCESS = "manage_beta_access"


_SUPPORT: frozenset[Capability] = frozenset({
    Capability.VIEW_USERS,
    Capability.VIEW_REPORTS,
    Capability.VIEW_CHATS,
    Capability.VIEW_FEEDBACK,
})

_ADMIN: frozenset[Capability] = frozenset({
    Capability.VIEW_USERS,
    Capability.VIEW_REPORTS,
    Capability.VIEW_AUDIT,
    Capability.VIEW_FEEDBACK,
    Capability.VIEW_GROWTH,
    Capability.EDIT_USER_PROFILE,
    Capability.RESET_DIAGNOSIS,
    Capability.RESET_CONVERSATIONS,
    Capability.CANCEL_DELETION,
    Capability.MANAGE_PRIVACY_REQUESTS,
})

# Super Admin holds every capability -- stated as "all of them" so a capability
# added later is automatically granted here and nowhere else by default.
_SUPER_ADMIN: frozenset[Capability] = frozenset(Capability)

CAPABILITIES: dict[PanelRole, frozenset[Capability]] = {
    PanelRole.SUPPORT: _SUPPORT,
    PanelRole.ADMIN: _ADMIN,
    PanelRole.SUPER_ADMIN: _SUPER_ADMIN,
}


def has_capability(role: PanelRole | None, capability: Capability) -> bool:
    """Never raises -- use for shaping a response (e.g. telling the UI what to show)."""
    if role is None:
        return False
    return capability in CAPABILITIES.get(role, frozenset())


def require(role: PanelRole | None, capability: Capability) -> None:
    """Enforce a capability. Raises AdminForbiddenError (403) when absent."""
    if not has_capability(role, capability):
        raise AdminForbiddenError(role.value if role else "anonymous", capability.value)


def capabilities_for(role: PanelRole | None) -> list[str]:
    """The role's capabilities, sorted -- returned to the UI so it can hide controls
    the backend would reject anyway."""
    if role is None:
        return []
    return sorted(c.value for c in CAPABILITIES.get(role, frozenset()))
