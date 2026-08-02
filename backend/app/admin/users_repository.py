"""Admin user-management persistence seam.

The InMemory implementation is the one the hermetic suite uses; it holds plain dicts
and applies the same filter/sort/paginate semantics the SQL implementation does, so
tests assert real behaviour rather than a stub.
"""

from __future__ import annotations

import abc
import threading
from datetime import datetime

from app.admin.users_models import (
    ConsentStatus,
    SortField,
    UserDetail,
    UserFilters,
    UserPage,
    UserStatus,
    UserSummary,
)


class AdminUserRepository(abc.ABC):
    @abc.abstractmethod
    def search(self, filters: UserFilters, *, page: int, page_size: int,
               sort_by: SortField, descending: bool) -> UserPage: ...

    @abc.abstractmethod
    def get_detail(self, founder_id: int) -> UserDetail | None: ...

    @abc.abstractmethod
    def get_summary(self, founder_id: int) -> UserSummary | None: ...

    @abc.abstractmethod
    def update_fields(self, founder_id: int, changes: dict, *, at: datetime
                      ) -> UserSummary: ...

    @abc.abstractmethod
    def reset_diagnosis(self, founder_id: int) -> int:
        """Clear diagnosis progress. Returns rows affected."""

    @abc.abstractmethod
    def reset_conversations(self, founder_id: int) -> int:
        """Clear chat history. Returns rows affected."""

    @abc.abstractmethod
    def set_subscription_expiry(self, founder_id: int, expires_at: datetime) -> bool:
        """Write the subscription expiry. Returns False when there is no
        subscription row to update, so the caller can report that honestly rather
        than claiming a change that did not happen."""


def _matches(u: UserSummary, f: UserFilters) -> bool:
    if f.search:
        needle = f.search.lower().strip()
        haystack = " ".join(str(x or "") for x in (
            u.full_name, u.email, u.phone, u.business_name, u.founder_id)).lower()
        if needle not in haystack:
            return False
    if f.status is not None and u.status != f.status:
        return False
    if f.subscription is not None and (u.plan_type or "") != f.subscription:
        return False
    if f.registered_after is not None and u.created_at < f.registered_after:
        return False
    if f.registered_before is not None and u.created_at > f.registered_before:
        return False
    if f.active_since is not None:
        if u.last_active_at is None or u.last_active_at < f.active_since:
            return False
    if f.diagnosis_completed is not None and u.diagnosis_completed != f.diagnosis_completed:
        return False
    if f.consent_status is not None and u.consent_status != f.consent_status:
        return False
    return True


class InMemoryAdminUserRepository(AdminUserRepository):
    def __init__(self, users: list[UserSummary] | None = None,
                 details: dict[int, UserDetail] | None = None) -> None:
        self._users: dict[int, UserSummary] = {u.founder_id: u for u in (users or [])}
        self._details: dict[int, UserDetail] = dict(details or {})
        self._resets: dict[int, list[str]] = {}
        self._expiries: dict[int, datetime] = {}
        self._lock = threading.RLock()

    def add(self, user: UserSummary) -> None:
        with self._lock:
            self._users[user.founder_id] = user

    def resets_for(self, founder_id: int) -> list[str]:
        """Test helper -- what was reset for this user."""
        return list(self._resets.get(founder_id, []))

    def search(self, filters: UserFilters, *, page: int, page_size: int,
               sort_by: SortField, descending: bool) -> UserPage:
        with self._lock:
            rows = [u for u in self._users.values() if _matches(u, filters)]

        def key(u: UserSummary):
            v = getattr(u, sort_by.value, None)
            if v is None:
                # None sorts last in both directions rather than exploding on a
                # datetime/str comparison.
                return (1, "")
            return (0, v.value if hasattr(v, "value") else v)

        rows.sort(key=key, reverse=descending)
        total = len(rows)
        start = (page - 1) * page_size
        return UserPage(items=rows[start:start + page_size], total=total,
                        page=page, page_size=page_size)

    def get_detail(self, founder_id: int) -> UserDetail | None:
        with self._lock:
            if founder_id not in self._users:
                return None
            return self._details.get(founder_id) or UserDetail(founder_id=founder_id)

    def get_summary(self, founder_id: int) -> UserSummary | None:
        with self._lock:
            return self._users.get(founder_id)

    def update_fields(self, founder_id: int, changes: dict, *, at: datetime) -> UserSummary:
        with self._lock:
            current = self._users[founder_id]
            data = {
                "founder_id": current.founder_id, "full_name": current.full_name,
                "email": current.email, "phone": current.phone,
                "business_name": current.business_name, "status": current.status,
                "plan_type": current.plan_type, "credits_balance": current.credits_balance,
                "diagnosis_completed": current.diagnosis_completed,
                "consent_status": current.consent_status, "created_at": current.created_at,
                "last_active_at": current.last_active_at,
            }
            for k, v in changes.items():
                if k in data:
                    data[k] = v
            updated = UserSummary(**data)
            self._users[founder_id] = updated
            return updated

    def reset_diagnosis(self, founder_id: int) -> int:
        with self._lock:
            self._resets.setdefault(founder_id, []).append("diagnosis")
            return 1

    def reset_conversations(self, founder_id: int) -> int:
        with self._lock:
            self._resets.setdefault(founder_id, []).append("conversations")
            return 1

    def set_subscription_expiry(self, founder_id: int, expires_at: datetime) -> bool:
        with self._lock:
            self._expiries[founder_id] = expires_at
            return True

    def expiry_for(self, founder_id: int):
        """Test helper."""
        return self._expiries.get(founder_id)
