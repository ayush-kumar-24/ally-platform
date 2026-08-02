"""Domain DTOs for admin user management."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    BANNED = "banned"


class ConsentStatus(str, Enum):
    GRANTED = "granted"          # consented, current document versions
    STALE = "stale"              # consented, but to superseded versions
    MISSING = "missing"          # never consented


class SortField(str, Enum):
    CREATED_AT = "created_at"
    LAST_ACTIVE_AT = "last_active_at"
    FULL_NAME = "full_name"
    EMAIL = "email"
    CREDITS_BALANCE = "credits_balance"
    STATUS = "status"


@dataclass(frozen=True)
class UserFilters:
    """Every field is optional; an unset field does not constrain the query.

    `search` is a single free-text box matched against name, email, phone, business
    name and founder id -- admins search for "the person", not "the column".
    """

    search: str | None = None
    status: UserStatus | None = None
    subscription: str | None = None
    registered_after: datetime | None = None
    registered_before: datetime | None = None
    active_since: datetime | None = None
    diagnosis_completed: bool | None = None
    consent_status: ConsentStatus | None = None


@dataclass(frozen=True)
class UserSummary:
    """One row in the users list."""

    founder_id: int
    full_name: str
    email: str
    phone: str | None
    business_name: str | None
    status: UserStatus
    plan_type: str | None
    credits_balance: int
    diagnosis_completed: bool
    consent_status: ConsentStatus
    created_at: datetime
    last_active_at: datetime | None = None


@dataclass(frozen=True)
class UserPage:
    items: list[UserSummary]
    total: int
    page: int
    page_size: int

    @property
    def pages(self) -> int:
        if self.page_size <= 0:
            return 0
        return (self.total + self.page_size - 1) // self.page_size


@dataclass(frozen=True)
class UserDetail:
    """The full admin view of one user.

    Sections are dicts/lists rather than typed models because they aggregate across
    a dozen tables whose shapes are owned elsewhere; forcing them into DTOs here
    would duplicate schemas that already exist and drift from them.
    """

    founder_id: int
    profile: dict[str, Any] = field(default_factory=dict)
    business: dict[str, Any] = field(default_factory=dict)
    subscription: dict[str, Any] | None = None
    credits: dict[str, Any] = field(default_factory=dict)
    consent: dict[str, Any] | None = None
    reports: list[dict] = field(default_factory=list)
    chat_count: int = 0
    diagnosis_history: list[dict] = field(default_factory=list)
    login_history: list[dict] = field(default_factory=list)
    privacy_requests: list[dict] = field(default_factory=list)
