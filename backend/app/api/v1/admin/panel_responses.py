"""Response models for the Admin Panel."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.admin.panel_audit import PanelAuditEvent
from app.admin.users_models import UserDetail, UserPage, UserSummary
from app.credits.models import CreditTransaction


class UserSummaryResponse(BaseModel):
    founder_id: int
    full_name: str
    email: str
    phone: str | None = None
    business_name: str | None = None
    status: str
    plan_type: str | None = None
    credits_balance: int
    diagnosis_completed: bool
    consent_status: str
    created_at: datetime
    last_active_at: datetime | None = None

    @classmethod
    def from_domain(cls, u: UserSummary) -> "UserSummaryResponse":
        return cls(founder_id=u.founder_id, full_name=u.full_name, email=u.email,
                   phone=u.phone, business_name=u.business_name, status=u.status.value,
                   plan_type=u.plan_type, credits_balance=u.credits_balance,
                   diagnosis_completed=u.diagnosis_completed,
                   consent_status=u.consent_status.value, created_at=u.created_at,
                   last_active_at=u.last_active_at)


class UserPageResponse(BaseModel):
    items: list[UserSummaryResponse]
    total: int
    page: int
    page_size: int
    pages: int

    @classmethod
    def from_domain(cls, p: UserPage) -> "UserPageResponse":
        return cls(items=[UserSummaryResponse.from_domain(u) for u in p.items],
                   total=p.total, page=p.page, page_size=p.page_size, pages=p.pages)


class UserDetailResponse(BaseModel):
    founder_id: int
    profile: dict[str, Any]
    business: dict[str, Any]
    subscription: dict[str, Any] | None = None
    credits: dict[str, Any]
    consent: dict[str, Any] | None = None
    reports: list[dict]
    chat_count: int
    diagnosis_history: list[dict]
    login_history: list[dict]
    privacy_requests: list[dict]

    @classmethod
    def from_domain(cls, d: UserDetail) -> "UserDetailResponse":
        return cls(founder_id=d.founder_id, profile=d.profile, business=d.business,
                   subscription=d.subscription, credits=d.credits, consent=d.consent,
                   reports=d.reports, chat_count=d.chat_count,
                   diagnosis_history=d.diagnosis_history, login_history=d.login_history,
                   privacy_requests=d.privacy_requests)


class CreditTransactionResponse(BaseModel):
    id: int
    user_id: int
    admin_id: int
    type: str
    amount: int
    balance_before: int
    balance_after: int
    reason: str
    created_at: datetime

    @classmethod
    def from_domain(cls, t: CreditTransaction) -> "CreditTransactionResponse":
        return cls(id=t.id, user_id=t.user_id, admin_id=t.admin_id, type=t.type.value,
                   amount=t.amount, balance_before=t.balance_before,
                   balance_after=t.balance_after, reason=t.reason, created_at=t.created_at)


class CreditAdjustResponse(BaseModel):
    transaction: CreditTransactionResponse
    balance: int          # the updated balance, surfaced at the top level
    message: str


class CreditLedgerResponse(BaseModel):
    items: list[CreditTransactionResponse]
    total: int
    balance: int


class AuditEventResponse(BaseModel):
    event_id: str
    admin_id: int
    admin_email: str
    admin_role: str
    action: str
    resource: str
    target_user_id: int | None = None
    old_value: str | None = None
    new_value: str | None = None
    ip_address: str | None = None
    result: str
    reason: str | None = None
    timestamp: datetime

    @classmethod
    def from_domain(cls, e: PanelAuditEvent) -> "AuditEventResponse":
        return cls(event_id=e.event_id, admin_id=e.admin_id, admin_email=e.admin_email,
                   admin_role=e.admin_role, action=e.action, resource=e.resource,
                   target_user_id=e.target_user_id, old_value=e.old_value,
                   new_value=e.new_value, ip_address=e.ip_address, result=e.result,
                   reason=e.reason, timestamp=e.timestamp)


class AuditPageResponse(BaseModel):
    items: list[AuditEventResponse]
    total: int
    limit: int
    offset: int


class WhoAmIResponse(BaseModel):
    """Lets the UI hide controls the backend would reject. The UI hiding them is
    convenience only -- the backend refuses regardless."""

    admin_id: int
    email: str
    role: str
    capabilities: list[str]
