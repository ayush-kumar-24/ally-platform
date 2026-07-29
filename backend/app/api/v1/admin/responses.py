"""Admin API response models with `from_domain` mappers."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class FounderResponse(BaseModel):
    founder_id: int
    full_name: str
    email: str
    status: str
    plan_type: str
    created_at: datetime
    conversation_count: int

    @classmethod
    def from_domain(cls, f) -> "FounderResponse":
        return cls(founder_id=f.founder_id, full_name=f.full_name, email=f.email,
                   status=f.status.value, plan_type=f.plan_type, created_at=f.created_at,
                   conversation_count=f.conversation_count)


class FounderListResponse(BaseModel):
    founders: list[FounderResponse]
    total: int


class ConversationResponse(BaseModel):
    conversation_id: str
    founder_id: int
    title: str
    status: str
    message_count: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, c) -> "ConversationResponse":
        return cls(conversation_id=c.conversation_id, founder_id=c.founder_id, title=c.title,
                   status=c.status, message_count=c.message_count, created_at=c.created_at,
                   updated_at=c.updated_at)


class ConversationListResponse(BaseModel):
    conversations: list[ConversationResponse]
    total: int


class FeedbackResponse(BaseModel):
    feedback_id: str
    suggestion_id: str
    founder_id: int
    feedback_type: str
    created_at: datetime

    @classmethod
    def from_domain(cls, f) -> "FeedbackResponse":
        return cls(feedback_id=f.feedback_id, suggestion_id=f.suggestion_id, founder_id=f.founder_id,
                   feedback_type=f.feedback_type, created_at=f.created_at)


class FeedbackListResponse(BaseModel):
    feedback: list[FeedbackResponse]
    total: int


class UsageResponse(BaseModel):
    messages_sent: int
    attachments_uploaded: int
    suggestions_generated: int


class DashboardResponse(BaseModel):
    total_founders: int
    active_founders: int
    suspended_founders: int
    new_founders: int
    total_conversations: int
    usage: UsageResponse
    daily_activity: int
    weekly_activity: int
    monthly_activity: int
    generated_at: datetime

    @classmethod
    def from_domain(cls, s) -> "DashboardResponse":
        return cls(
            total_founders=s.total_founders, active_founders=s.active_founders,
            suspended_founders=s.suspended_founders, new_founders=s.new_founders,
            total_conversations=s.total_conversations,
            usage=UsageResponse(messages_sent=s.usage.messages_sent,
                                attachments_uploaded=s.usage.attachments_uploaded,
                                suggestions_generated=s.usage.suggestions_generated),
            daily_activity=s.daily_activity, weekly_activity=s.weekly_activity,
            monthly_activity=s.monthly_activity, generated_at=s.generated_at)


class AnnouncementResponse(BaseModel):
    announcement_id: str
    title: str
    body: str
    audience: str
    created_by: int
    created_at: datetime
    active: bool

    @classmethod
    def from_domain(cls, a) -> "AnnouncementResponse":
        return cls(announcement_id=a.announcement_id, title=a.title, body=a.body,
                   audience=a.audience, created_by=a.created_by, created_at=a.created_at,
                   active=a.active)


class AnnouncementListResponse(BaseModel):
    announcements: list[AnnouncementResponse]
    total: int


class AuditEventResponse(BaseModel):
    event_id: str
    admin_id: int
    action: str
    resource: str
    timestamp: datetime
    result: str
    reason: str | None

    @classmethod
    def from_domain(cls, e) -> "AuditEventResponse":
        return cls(event_id=e.event_id, admin_id=e.admin_id, action=e.action, resource=e.resource,
                   timestamp=e.timestamp, result=e.result, reason=e.reason)


class AuditListResponse(BaseModel):
    events: list[AuditEventResponse]
    total: int
