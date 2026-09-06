"""In-app notifications feed.

    GET  /notifications                list the founder's in-app notifications (+ unread count)
    POST /notifications/{id}/read      mark one read
    POST /notifications/read-all       mark all read

This is the notification *feed* (the bell). It is separate from notification
*preferences* (which toggles are on), which live under /settings/notifications.
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_founder_record
from app.db.session import get_db
from app.middleware.error_handler import AppError
from app.models import Founder
from app.repositories import notification_repository
from app.schemas.notification import NotificationListResponse, NotificationRead

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationNotFoundError(AppError):
    def __init__(self):
        super().__init__("Notification not found", status_code=status.HTTP_404_NOT_FOUND)


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    unread_only: bool = False,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
):
    """The founder's notifications, newest first, plus the unread badge count."""
    items = notification_repository.list_for_founder(
        db, founder.founder_id, unread_only=unread_only, limit=limit, offset=offset
    )
    return NotificationListResponse(
        items=items,
        unread_count=notification_repository.unread_count(db, founder.founder_id),
    )


@router.post("/{notification_id}/read", response_model=NotificationRead)
async def mark_read(
    notification_id: int,
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
):
    notification = notification_repository.get(db, notification_id)
    # Never touch or reveal another founder's notification.
    if notification is None or notification.founder_id != founder.founder_id:
        raise NotificationNotFoundError()
    return notification_repository.mark_read(db, notification)


@router.post("/read-all")
async def mark_all_read(
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
):
    changed = notification_repository.mark_all_read(db, founder.founder_id)
    return {"marked_read": changed}
