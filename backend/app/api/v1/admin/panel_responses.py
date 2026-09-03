"""Response models for the Admin Panel."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.admin.health import ComponentHealth, HealthReport
from app.admin.insights import Metric
from app.admin.panel_audit import PanelAuditEvent
from app.admin.users_models import UserDetail, UserPage, UserSummary
from app.credits.models import CreditTransaction
from app.privacy.models import PrivacyAction


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


class PrivacyRequestResponse(BaseModel):
    request_id: int
    founder_id: int
    request_type: str
    status: str
    requested_at: datetime
    due_by: datetime | None = None
    request_details: str | None = None
    processed_by: str | None = None
    processing_notes: str | None = None
    rejection_reason: str | None = None
    completed_at: datetime | None = None

    @classmethod
    def from_domain(cls, a: PrivacyAction) -> "PrivacyRequestResponse":
        return cls(request_id=a.request_id, founder_id=a.founder_id,
                   request_type=a.request_type, status=a.status,
                   requested_at=a.requested_at, due_by=a.due_by,
                   request_details=a.request_details, processed_by=a.processed_by,
                   processing_notes=a.processing_notes, rejection_reason=a.rejection_reason,
                   completed_at=a.completed_at)


class PrivacyRequestListResponse(BaseModel):
    items: list[PrivacyRequestResponse]
    total: int

    @classmethod
    def from_domain(cls, items: list[PrivacyAction]) -> "PrivacyRequestListResponse":
        return cls(items=[PrivacyRequestResponse.from_domain(a) for a in items], total=len(items))


class WhoAmIResponse(BaseModel):
    """Lets the UI hide controls the backend would reject. The UI hiding them is
    convenience only -- the backend refuses regardless."""

    admin_id: int
    email: str
    role: str
    capabilities: list[str]


class MetricResponse(BaseModel):
    """One dashboard card. `available=False` means "could not be measured" --
    see `Metric`'s own docstring on why that is shown as "--", not a false 0."""

    key: str
    label: str
    value: float | int | None
    unit: str = ""
    available: bool
    unavailable_reason: str | None = None

    @classmethod
    def from_domain(cls, m: Metric) -> "MetricResponse":
        return cls(key=m.key, label=m.label, value=m.value, unit=m.unit,
                   available=m.available, unavailable_reason=m.unavailable_reason)


class DashboardMetricsResponse(BaseModel):
    items: list[MetricResponse]

    @classmethod
    def from_domain(cls, metrics: list[Metric]) -> "DashboardMetricsResponse":
        return cls(items=[MetricResponse.from_domain(m) for m in metrics])


class ComponentHealthResponse(BaseModel):
    key: str
    label: str
    status: str
    detail: str = ""

    @classmethod
    def from_domain(cls, c: ComponentHealth) -> "ComponentHealthResponse":
        return cls(key=c.key, label=c.label, status=c.status.value, detail=c.detail)


class HealthReportResponse(BaseModel):
    """`status` is green/amber/red -- worst of every component below, not an
    average (see HealthReport.status's own docstring)."""

    status: str
    components: list[ComponentHealthResponse]
    checked_at: datetime

    @classmethod
    def from_domain(cls, r: HealthReport) -> "HealthReportResponse":
        return cls(status=r.status.value,
                   components=[ComponentHealthResponse.from_domain(c) for c in r.components],
                   checked_at=r.checked_at)
