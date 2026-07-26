from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationRead(BaseModel):
    """One in-app notification as the bell/feed shows it."""

    model_config = ConfigDict(from_attributes=True)

    notification_id: int
    type: str
    title: str
    body: str
    action_url: str | None = None
    is_read: bool
    read_at: datetime | None = None
    created_at: datetime | None = None


class NotificationListResponse(BaseModel):
    items: list[NotificationRead]
    unread_count: int
