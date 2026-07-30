"""Admin domain models (Phase 12, Part 1). Immutable frozen dataclasses -- the admin
view over existing data plus admin-owned records (announcements, audit)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class AdminRole(str, Enum):
    READ_ONLY = "read_only"
    OPERATOR = "operator"
    ADMIN = "admin"


class FounderStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


@dataclass(frozen=True)
class AdminUser:
    admin_id: int
    email: str
    role: AdminRole


@dataclass(frozen=True)
class FounderSummary:
    founder_id: int
    full_name: str
    email: str
    status: FounderStatus
    plan_type: str
    created_at: datetime
    conversation_count: int = 0


@dataclass(frozen=True)
class ConversationSummary:
    conversation_id: str
    founder_id: int
    title: str
    status: str
    message_count: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class FeedbackSummary:
    feedback_id: str
    suggestion_id: str
    founder_id: int
    feedback_type: str
    created_at: datetime


@dataclass(frozen=True)
class UsageMetrics:
    messages_sent: int = 0
    attachments_uploaded: int = 0
    suggestions_generated: int = 0


@dataclass(frozen=True)
class SystemStats:
    total_founders: int
    active_founders: int
    suspended_founders: int
    new_founders: int                # created within the recent window (7 days)
    total_conversations: int
    usage: UsageMetrics
    daily_activity: int              # conversations created in the last 1 / 7 / 30 days
    weekly_activity: int
    monthly_activity: int
    generated_at: datetime


@dataclass(frozen=True)
class Announcement:
    announcement_id: str
    title: str
    body: str
    audience: str
    created_by: int
    created_at: datetime
    active: bool = True


@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    admin_id: int
    action: str
    resource: str
    timestamp: datetime
    result: str                      # "success" | "failure"
    reason: str | None = None
