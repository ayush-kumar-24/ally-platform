from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.schema import Notifications
from app.repositories.base import BaseRepository

# The feed shows in-app notifications only; email-channel rows are for delivery.
_CHANNEL = "in_app"


class NotificationRepository(BaseRepository[Notifications]):
    def __init__(self) -> None:
        super().__init__(Notifications)

    def list_for_founder(
        self, db: Session, founder_id: int, *, unread_only: bool = False,
        limit: int = 50, offset: int = 0,
    ) -> list[Notifications]:
        stmt = (
            select(Notifications)
            .where(
                Notifications.founder_id == founder_id,
                Notifications.channel == _CHANNEL,
                # Dismissed rows stay in the table so their dedup_key keeps
                # suppressing regeneration; they just stop being shown.
                Notifications.dismissed_at.is_(None),
            )
        )
        if unread_only:
            stmt = stmt.where(Notifications.is_read.is_(False))
        stmt = stmt.order_by(Notifications.created_at.desc()).limit(limit).offset(offset)
        return list(db.execute(stmt).scalars().all())

    def unread_count(self, db: Session, founder_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(Notifications)
            .where(
                Notifications.founder_id == founder_id,
                Notifications.channel == _CHANNEL,
                Notifications.is_read.is_(False),
                Notifications.dismissed_at.is_(None),
            )
        )
        return db.execute(stmt).scalar_one()

    def mark_read(self, db: Session, notification: Notifications) -> Notifications:
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(notification)
        return notification

    def mark_all_read(self, db: Session, founder_id: int) -> int:
        """Mark every unread in-app notification read. Returns how many changed."""
        stmt = (
            update(Notifications)
            .where(
                Notifications.founder_id == founder_id,
                Notifications.channel == _CHANNEL,
                Notifications.is_read.is_(False),
            )
            .values(is_read=True, read_at=datetime.now(timezone.utc))
        )
        result = db.execute(stmt)
        db.commit()
        return result.rowcount

    def dismiss_all(self, db: Session, founder_id: int) -> int:
        """Clear the panel. Returns how many rows were hidden.

        Marks read as well as dismissed. A row that is hidden but still counted
        as unread would leave the bell badged with a number nothing on screen
        explains -- which is the current bug, in reverse.
        """
        now = datetime.now(timezone.utc)
        stmt = (
            update(Notifications)
            .where(
                Notifications.founder_id == founder_id,
                Notifications.channel == _CHANNEL,
                Notifications.dismissed_at.is_(None),
            )
            .values(dismissed_at=now, is_read=True, read_at=Notifications.read_at)
        )
        result = db.execute(stmt)
        db.commit()
        return result.rowcount


notification_repository = NotificationRepository()
