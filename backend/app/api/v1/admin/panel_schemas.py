"""Request models for the Admin Panel. `extra="forbid"` fails closed."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.admin.users_models import UserStatus
from app.credits.models import CreditOperation


class UserUpdateRequest(BaseModel):
    """Partial update. Only the sent fields change, and each one is authorized
    independently by the service (renaming != suspending)."""

    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=20)
    business_name: str | None = Field(default=None, max_length=200)
    admin_notes: str | None = Field(default=None, max_length=5000)
    status: UserStatus | None = None


class StatusChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: UserStatus
    reason: str | None = Field(default=None, max_length=500)


class CreditAdjustRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: CreditOperation
    # ge=0 at the schema too: a negative "remove" would be an add in disguise.
    amount: int = Field(ge=0, le=1_000_000)
    reason: str = Field(min_length=1, max_length=500)


class SubscriptionUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: str | None = Field(default=None, max_length=30)
    expires_at: datetime | None = None
    monthly_credits: int | None = Field(default=None, ge=0, le=1_000_000)
    bonus_credits: int | None = Field(default=None, ge=0, le=1_000_000)


class PrivacyRequestResolveRequest(BaseModel):
    """Resolve one queued Privacy Center request. `status` is restricted to
    the three outcomes an admin can move a request TO -- 'pending' is not
    listed because that's only the state a request starts in, never a
    resolution."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["in_progress", "completed", "rejected"]
    processing_notes: str | None = Field(default=None, max_length=5000)
    rejection_reason: str | None = Field(default=None, max_length=1000)


class ConfirmRequest(BaseModel):
    """Destructive actions must be confirmed explicitly -- a stray or retried POST
    must not be able to wipe a user's history."""

    model_config = ConfigDict(extra="forbid")

    confirm: bool = False
    reason: str | None = Field(default=None, max_length=500)
