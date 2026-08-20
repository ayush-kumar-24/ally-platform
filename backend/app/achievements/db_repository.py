"""SQLAlchemy-backed AchievementRepository (production).

Maps ORM rows <-> frozen domain models. Untested in the hermetic suite (no
live DB); mirrors the app's other repositories. `total_messages` is a raw
read against `conversations` -- same pattern as
app/api/v1/dashboard/repository.py's other cross-table aggregate reads.
"""

from __future__ import annotations

from sqlalchemy import text

from app.achievements.db_models import AchievementRow
from app.achievements.models import Achievement
from app.achievements.repository import AchievementRepository


def _to_domain(row: AchievementRow) -> Achievement:
    return Achievement(
        achievement_id=row.achievement_id,
        founder_id=row.founder_id,
        title=row.title,
        description=row.description,
        category=row.category,
        occurred_on=row.occurred_on,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAlchemyAchievementRepository(AchievementRepository):
    def __init__(self, db):
        self.db = db

    def add(self, achievement: Achievement) -> Achievement:
        row = AchievementRow(
            achievement_id=achievement.achievement_id,
            founder_id=achievement.founder_id,
            title=achievement.title,
            description=achievement.description,
            category=achievement.category,
            occurred_on=achievement.occurred_on,
            created_at=achievement.created_at,
            updated_at=achievement.updated_at,
        )
        self.db.add(row)
        self.db.commit()
        return achievement

    def get(self, achievement_id: str) -> Achievement | None:
        row = self.db.get(AchievementRow, achievement_id)
        return _to_domain(row) if row is not None else None

    def replace(self, achievement: Achievement) -> Achievement:
        row = self.db.get(AchievementRow, achievement.achievement_id)
        if row is None:
            return self.add(achievement)
        row.title = achievement.title
        row.description = achievement.description
        row.category = achievement.category
        row.occurred_on = achievement.occurred_on
        row.updated_at = achievement.updated_at
        self.db.commit()
        return achievement

    def list_for_founder(self, founder_id: int) -> tuple[Achievement, ...]:
        rows = (
            self.db.query(AchievementRow)
            .filter(AchievementRow.founder_id == founder_id)
            .order_by(AchievementRow.created_at.desc(), AchievementRow.achievement_id.desc())
            .all()
        )
        return tuple(_to_domain(r) for r in rows)

    def delete(self, achievement_id: str) -> None:
        row = self.db.get(AchievementRow, achievement_id)
        if row is not None:
            self.db.delete(row)
            self.db.commit()

    def total_messages(self, founder_id: int) -> int:
        result = self.db.execute(
            text("SELECT COALESCE(SUM(message_count), 0) FROM conversations WHERE founder_id = :f"),
            {"f": founder_id},
        ).scalar()
        return int(result or 0)
