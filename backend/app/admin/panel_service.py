"""AdminPanelService -- every admin action passes through here.

Two invariants this layer exists to guarantee:

1. **Authorization is checked before the mutation, in the service.** Not in the
   router, not in the UI. A capability check that lives in the endpoint can be
   bypassed by any new caller; one that lives here cannot be bypassed at all.

2. **Every mutation is audited with its before and after.** The audit write happens
   after the change succeeds and is not wrapped in a try/except -- if the audit
   cannot be written the request fails, because an unrecorded admin action is
   exactly the thing this panel exists to prevent.

Note on PATCH: the required capability depends on WHICH fields are being changed,
not on the endpoint. Renaming a user is an Admin-level edit; suspending one is
Super-Admin-only. Deciding that per-field here means a single endpoint can't be used
to smuggle a privileged change through an unprivileged path.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from app.admin.errors import AdminFounderNotFoundError, InvalidSearchError
from app.admin.panel_audit import AuditRecorder
from app.admin.rbac import Capability, PanelRole, require
from app.admin.users_models import (
    SortField,
    UserDetail,
    UserFilters,
    UserPage,
    UserStatus,
    UserSummary,
)
from app.admin.users_repository import AdminUserRepository
from app.credits.models import CreditOperation, CreditTransaction
from app.credits.service import CreditService

MAX_PAGE_SIZE = 100

# Which capability each PATCH field demands.
_FIELD_CAPABILITY: dict[str, Capability] = {
    "full_name": Capability.EDIT_USER_PROFILE,
    "email": Capability.EDIT_USER_PROFILE,
    "phone": Capability.EDIT_USER_PROFILE,
    "business_name": Capability.EDIT_USER_PROFILE,
    "admin_notes": Capability.EDIT_USER_PROFILE,
    "status": Capability.SUSPEND_USER,        # activate/deactivate/suspend/ban
    "role": Capability.CHANGE_USER_ROLE,
    "plan_type": Capability.MODIFY_SUBSCRIPTION,
}


class AdminPanelService:
    def __init__(
        self,
        users: AdminUserRepository,
        *,
        credits: CreditService,
        audit: AuditRecorder,
        clock: Callable[[], datetime] | None = None,
        conversations=None,
        report_regenerator: Callable[[int], dict] | None = None,
        privacy=None,
        feedback=None,
        health=None,
    ):
        self.users = users
        self.credits = credits
        self.audit = audit
        # Optional collaborators -- the panel works without them; the endpoints that
        # need them report that they are unconfigured rather than failing obscurely.
        self.conversations = conversations
        self.report_regenerator = report_regenerator
        self.privacy = privacy  # PrivacyRepository -- backs cancel_pending_deletion
        self.feedback = feedback  # FeedbackReadRepository -- backs list_feedback/feedback_stats
        # HealthChecker -- backs system_health. Read-only: the panel page never
        # sends an alert itself, that side effect lives only in the scheduled
        # /internal/jobs/check-health path (see that router's docstring) --
        # a GET an admin loads to look at the page should not also page someone.
        self.health = health
        self._now = clock or (lambda: datetime.now(timezone.utc))

    # --- reads ------------------------------------------------------------

    def list_users(self, admin, *, filters: UserFilters | None = None, page: int = 1,
                   page_size: int = 25, sort_by: SortField = SortField.CREATED_AT,
                   descending: bool = True) -> UserPage:
        require(admin.role, Capability.VIEW_USERS)
        page = max(1, page)
        page_size = max(1, min(page_size, MAX_PAGE_SIZE))
        return self.users.search(filters or UserFilters(), page=page, page_size=page_size,
                                 sort_by=sort_by, descending=descending)

    def get_user(self, admin, founder_id: int) -> UserDetail:
        require(admin.role, Capability.VIEW_USERS)
        detail = self.users.get_detail(founder_id)
        if detail is None:
            raise AdminFounderNotFoundError(founder_id)
        return detail

    def system_health(self, admin):
        """Admin Panel proposal Phase 3: the Health page -- database, AI
        provider, report engine, storage, error rate, green/amber/red.

        Same read tier as dashboard_metrics: operational status, not
        per-founder data, so Support reads it too -- "if the database breaks,
        we find out from a customer" was the whole point of this gap, and
        that includes Support, who are the ones actually talking to the
        customer first.
        """
        require(admin.role, Capability.VIEW_USERS)
        if self.health is None:
            raise InvalidSearchError("health checks are not configured")
        return self.health.check()

    # --- user mutations ---------------------------------------------------

    def update_user(self, admin, founder_id: int, changes: dict[str, Any], *,
                    ip: str | None = None) -> UserSummary:
        """Apply a partial update. Each field is authorized independently."""
        if not changes:
            return self._require_user(founder_id)

        for field in changes:
            capability = _FIELD_CAPABILITY.get(field)
            if capability is None:
                # Unknown field -> refuse rather than silently drop, so a caller is
                # never told "updated" about something that was ignored.
                raise InvalidSearchError(f"field '{field}' is not updatable")
            require(admin.role, capability)

        before = self._require_user(founder_id)
        after = self.users.update_fields(founder_id, changes, at=self._now())
        self.audit.record(
            admin=admin, action="user.update", resource=f"founder:{founder_id}",
            target_user_id=founder_id, ip_address=ip,
            old_value={k: _plain(getattr(before, k, None)) for k in changes},
            new_value={k: _plain(v) for k, v in changes.items()},
        )
        return after

    def set_status(self, admin, founder_id: int, status: UserStatus, *,
                   reason: str | None = None, ip: str | None = None) -> UserSummary:
        require(admin.role, Capability.SUSPEND_USER)
        before = self._require_user(founder_id)
        after = self.users.update_fields(founder_id, {"status": status}, at=self._now())
        self.audit.record(
            admin=admin, action=f"user.{status.value}", resource=f"founder:{founder_id}",
            target_user_id=founder_id, ip_address=ip, reason=reason,
            old_value=before.status.value, new_value=status.value)
        return after

    def reset_diagnosis(self, admin, founder_id: int, *, ip: str | None = None) -> int:
        require(admin.role, Capability.RESET_DIAGNOSIS)
        self._require_user(founder_id)
        affected = self.users.reset_diagnosis(founder_id)
        self.audit.record(admin=admin, action="user.reset_diagnosis",
                          resource=f"founder:{founder_id}", target_user_id=founder_id,
                          ip_address=ip, new_value={"rows_affected": affected})
        return affected

    def reset_conversations(self, admin, founder_id: int, *, ip: str | None = None) -> int:
        require(admin.role, Capability.RESET_CONVERSATIONS)
        self._require_user(founder_id)
        affected = self.users.reset_conversations(founder_id)
        self.audit.record(admin=admin, action="user.reset_conversations",
                          resource=f"founder:{founder_id}", target_user_id=founder_id,
                          ip_address=ip, new_value={"rows_affected": affected})
        return affected

    def cancel_pending_deletion(self, admin, founder_id: int, *, reason: str,
                                ip: str | None = None):
        """Clear a founder's scheduled erasure before the sweep runs.

        The one case this exists for: a Supabase-webhook-triggered deletion,
        where the founder structurally cannot log back in to cancel it
        themselves (their identity is already gone) and their only recourse
        is contacting support out-of-band. `reason` is required (not
        optional, unlike most audited actions here) because reversing an
        erasure request is exactly the kind of action that needs a human
        explanation on the record, not just a timestamp.
        """
        require(admin.role, Capability.CANCEL_DELETION)
        if self.privacy is None:
            raise InvalidSearchError("deletion cancellation is not configured")
        self._require_user(founder_id)
        state = self.privacy.cancel_deletion(founder_id)
        self.audit.record(
            admin=admin, action="user.cancel_deletion", resource=f"founder:{founder_id}",
            target_user_id=founder_id, ip_address=ip, reason=reason,
            old_value="deletion_pending", new_value="cancelled",
        )
        return state

    # --- privacy requests (DSAR fulfilment) --------------------------------

    def list_privacy_requests(self, admin, *, status: str | None = None,
                              limit: int = 50, offset: int = 0):
        """The review queue behind the Privacy Center's "Request"-type actions
        (view_data, correct_data, etc.). Read-only -- same tier as VIEW_USERS,
        since this is what makes those requests visible to anyone at all."""
        require(admin.role, Capability.VIEW_USERS)
        if self.privacy is None:
            raise InvalidSearchError("privacy request review is not configured")
        return self.privacy.list_all_requests(status=status, limit=limit, offset=offset)

    def resolve_privacy_request(self, admin, request_id: int, *, status: str,
                                processing_notes: str | None = None,
                                rejection_reason: str | None = None,
                                ip: str | None = None):
        """Move a queued request to in_progress/completed/rejected.

        Before this existed, every "View data summary" / "Request data
        correction" click created a privacy_requests row that could never be
        marked done by anything in the codebase -- this is that missing path.
        """
        require(admin.role, Capability.MANAGE_PRIVACY_REQUESTS)
        if self.privacy is None:
            raise InvalidSearchError("privacy request review is not configured")
        before = None
        for r in self.privacy.list_all_requests(limit=1000):
            if r.request_id == request_id:
                before = r
                break
        updated = self.privacy.resolve_request(
            request_id, status=status, processed_by=admin.email,
            processing_notes=processing_notes, rejection_reason=rejection_reason,
            at=self._now(),
        )
        self.audit.record(
            admin=admin, action="privacy_request.resolve",
            resource=f"privacy_request:{request_id}",
            target_user_id=updated.founder_id, ip_address=ip,
            old_value=before.status if before else None, new_value=status,
        )
        return updated

    def delete_user(self, admin, founder_id: int, *, reason: str | None = None,
                    ip: str | None = None) -> UserSummary:
        """Soft-delete by banning. A hard DELETE is deliberately not offered here:
        it would cascade across ~100 tables irreversibly from a single HTTP call,
        and erasure already has a governed path in the Privacy Center."""
        require(admin.role, Capability.DELETE_USER)
        before = self._require_user(founder_id)
        after = self.users.update_fields(founder_id, {"status": UserStatus.BANNED},
                                         at=self._now())
        self.audit.record(admin=admin, action="user.delete", resource=f"founder:{founder_id}",
                          target_user_id=founder_id, ip_address=ip, reason=reason,
                          old_value=before.status.value, new_value=UserStatus.BANNED.value)
        return after

    # --- credits ----------------------------------------------------------

    def adjust_credits(self, admin, founder_id: int, *, operation: CreditOperation,
                       amount: int, reason: str, ip: str | None = None) -> CreditTransaction:
        """Super Admin only -- enforced here, so no route can grant it by omission."""
        require(admin.role, Capability.TRANSFER_CREDITS)
        self._require_user(founder_id)
        tx = self.credits.adjust(founder_id, admin_id=admin.admin_id, operation=operation,
                                 amount=amount, reason=reason)
        self.audit.record(
            admin=admin, action=f"credits.{operation.value}",
            resource=f"founder:{founder_id}", target_user_id=founder_id, ip_address=ip,
            reason=reason, old_value={"balance": tx.balance_before},
            new_value={"balance": tx.balance_after, "delta": tx.amount,
                       "transaction_id": tx.id})
        return tx

    def list_credit_transactions(self, admin, founder_id: int, *, limit: int = 50,
                                 offset: int = 0):
        require(admin.role, Capability.VIEW_USERS)
        return self.credits.list_transactions(founder_id, limit=limit, offset=offset)

    # --- bulk credits ------------------------------------------------------

    def bulk_adjust_credits(self, admin, *, operation: CreditOperation, amount: int,
                            reason: str, founder_ids: list[int] | None = None,
                            filters: UserFilters | None = None,
                            dry_run: bool = False, ip: str | None = None) -> dict:
        """Apply one credit operation to a cohort.

        Target either an explicit `founder_ids` list or everyone matching `filters`
        (e.g. all Pro users). Exactly one must be given -- accepting both invites a
        silent mismatch between what the admin previewed and what ran.

        **Per-user isolation.** Each founder is adjusted in its own transaction, and
        a failure for one (say, REMOVE below zero) is recorded and skipped rather
        than aborting the run. One rolled-back batch of 500 because user #312 was
        short 5 credits would be worse than applying the other 499 and reporting the
        one that failed.

        **dry_run** resolves the cohort and returns it without writing anything, so
        "grant 100 to all Pro users" can be checked before it is irreversible.
        """
        require(admin.role, Capability.TRANSFER_CREDITS)

        if (founder_ids is None) == (filters is None):
            raise InvalidSearchError("provide exactly one of founder_ids or filters")

        if founder_ids is not None:
            targets = list(dict.fromkeys(founder_ids))       # de-dupe, keep order
        else:
            targets, page = [], 1
            while True:
                # Page through so a large cohort isn't capped by MAX_PAGE_SIZE.
                batch = self.users.search(filters, page=page, page_size=MAX_PAGE_SIZE,
                                          sort_by=SortField.CREATED_AT, descending=False)
                targets.extend(u.founder_id for u in batch.items)
                if page >= batch.pages or not batch.items:
                    break
                page += 1

        if dry_run:
            return {"dry_run": True, "matched": len(targets), "founder_ids": targets,
                    "operation": operation.value, "amount": amount}

        applied, failed = [], []
        for fid in targets:
            try:
                tx = self.credits.adjust(fid, admin_id=admin.admin_id, operation=operation,
                                         amount=amount, reason=reason)
                applied.append({"founder_id": fid, "balance_after": tx.balance_after,
                                "transaction_id": tx.id})
            except Exception as exc:                          # noqa: BLE001 - reported, not hidden
                failed.append({"founder_id": fid, "error": str(exc)})

        # One audit row for the batch, carrying the counts and the reason. Each
        # individual movement already has its own immutable ledger row.
        self.audit.record(
            admin=admin, action=f"credits.bulk_{operation.value}",
            resource=f"cohort:{len(targets)}", ip_address=ip, reason=reason,
            result="success" if not failed else "partial",
            new_value={"operation": operation.value, "amount": amount,
                       "targeted": len(targets), "applied": len(applied),
                       "failed": len(failed)})

        return {"dry_run": False, "targeted": len(targets), "applied": applied,
                "failed": failed, "succeeded": len(applied), "failure_count": len(failed)}

    # --- subscription ------------------------------------------------------

    def update_subscription(self, admin, founder_id: int, *, plan: str | None = None,
                            expires_at: datetime | None = None,
                            monthly_credits: int | None = None,
                            bonus_credits: int | None = None,
                            ip: str | None = None) -> dict:
        """Change plan/expiry and optionally grant credits.

        Credit grants route through the ledger rather than writing a balance, so a
        subscription change leaves the same auditable trail as a manual adjustment.
        """
        require(admin.role, Capability.MODIFY_SUBSCRIPTION)
        before = self._require_user(founder_id)

        changed: dict[str, Any] = {}
        if plan is not None:
            self.users.update_fields(founder_id, {"plan_type": plan}, at=self._now())
            changed["plan"] = plan
        if expires_at is not None:
            # Report whether it actually landed -- a founder with no subscription row
            # has nothing to update, and claiming otherwise would be a lie in the log.
            written = self.users.set_subscription_expiry(founder_id, expires_at)
            changed["expires_at"] = {"value": expires_at.isoformat(), "applied": written}

        for label, value, op in (("monthly_credits", monthly_credits, CreditOperation.ADD),
                                 ("bonus_credits", bonus_credits, CreditOperation.BONUS)):
            if value:
                require(admin.role, Capability.TRANSFER_CREDITS)
                tx = self.credits.adjust(founder_id, admin_id=admin.admin_id, operation=op,
                                         amount=value, reason=f"Subscription {label} grant")
                changed[label] = {"granted": value, "balance_after": tx.balance_after}

        self.audit.record(admin=admin, action="subscription.update",
                          resource=f"founder:{founder_id}", target_user_id=founder_id,
                          ip_address=ip,
                          old_value={"plan": before.plan_type,
                                     "balance": before.credits_balance},
                          new_value=changed)
        return {"founder_id": founder_id, "changes": changed}

    # --- conversation viewer (read-only) -----------------------------------

    def list_conversations(self, admin, founder_id: int, *, limit: int = 50,
                           offset: int = 0):
        require(admin.role, Capability.VIEW_CHATS)
        self._require_user(founder_id)
        return self.conversations.list_for_founder(founder_id, limit=limit, offset=offset)

    def view_conversation(self, admin, conversation_id: str):
        """Read a conversation's messages.

        Support holds VIEW_CHATS and can read this. There is deliberately no write
        counterpart anywhere in this service -- the requirement is that support can
        view but never edit, and the safest way to guarantee that is to not build
        the mutation at all rather than to guard one.
        """
        require(admin.role, Capability.VIEW_CHATS)
        return self.conversations.get_with_messages(conversation_id)

    # --- feedback (read-only) -----------------------------------------------

    def list_feedback(self, admin, *, feedback_type: str | None = None,
                      limit: int = 50, offset: int = 0):
        """Star ratings and written notes, newest first -- every founder
        submission previously landed in founder_feedback with no admin-visible
        read path at all (the older GET /admin/feedback route existed but was
        wired to an in-memory stub, live-verified to return nothing even with
        real rows in the database). This is the real one."""
        require(admin.role, Capability.VIEW_FEEDBACK)
        if self.feedback is None:
            raise InvalidSearchError("feedback review is not configured")
        return self.feedback.list_feedback(feedback_type=feedback_type, limit=limit, offset=offset)

    def feedback_stats(self, admin, *, feedback_type: str | None = None):
        """Aggregate counts (total, how many carry a rating, average rating,
        breakdown by type) over the same filter list_feedback uses."""
        require(admin.role, Capability.VIEW_FEEDBACK)
        if self.feedback is None:
            raise InvalidSearchError("feedback review is not configured")
        return self.feedback.stats(feedback_type=feedback_type)

    # --- report regeneration ------------------------------------------------

    def regenerate_report(self, admin, founder_id: int, *, reason: str | None = None,
                          ip: str | None = None) -> dict:
        """Re-run report generation for a founder (after a prompt/model change).

        The generator is injected rather than imported, so this module stays
        decoupled from report internals and the action is testable offline.
        """
        require(admin.role, Capability.RESET_DIAGNOSIS)
        self._require_user(founder_id)
        if self.report_regenerator is None:
            raise InvalidSearchError("report regeneration is not configured")

        result = self.report_regenerator(founder_id)
        self.audit.record(admin=admin, action="report.regenerate",
                          resource=f"founder:{founder_id}", target_user_id=founder_id,
                          ip_address=ip, reason=reason, new_value=result)
        return {"founder_id": founder_id, "result": result}

    # --- audit -------------------------------------------------------------

    def list_audit(self, admin, *, limit: int = 100, offset: int = 0,
                   target_user_id: int | None = None, action: str | None = None):
        require(admin.role, Capability.VIEW_AUDIT)
        return self.audit.repository.list(limit=limit, offset=offset,
                                          target_user_id=target_user_id, action=action)

    # --- internals ---------------------------------------------------------

    def _require_user(self, founder_id: int) -> UserSummary:
        user = self.users.get_summary(founder_id)
        if user is None:
            raise AdminFounderNotFoundError(founder_id)
        return user


def _plain(value):
    return value.value if hasattr(value, "value") else value
