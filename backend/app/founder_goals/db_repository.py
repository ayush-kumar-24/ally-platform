"""SQLAlchemy-backed FounderGoalRepository (production).

Maps ORM rows <-> frozen domain models. Untested in the hermetic suite (no
live DB); mirrors the app's other repositories (commit + return the domain
object). See app/consents/db_repository.py / app/planning/db_repository.py.
"""

from __future__ import annotations

from app.founder_goals.db_models import FounderGoalRow
from app.founder_goals.models import FounderGoal
from app.founder_goals.repository import FounderGoalRepository


def _to_domain(row: FounderGoalRow) -> FounderGoal:
    return FounderGoal(
        goal_id=row.goal_id,
        founder_id=row.founder_id,
        title=row.title,
        subtitle=row.subtitle,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAlchemyFounderGoalRepository(FounderGoalRepository):
    def __init__(self, db):
        self.db = db

    def add(self, goal: FounderGoal) -> FounderGoal:
        row = FounderGoalRow(
            goal_id=goal.goal_id,
            founder_id=goal.founder_id,
            title=goal.title,
            subtitle=goal.subtitle,
            created_at=goal.created_at,
            updated_at=goal.updated_at,
        )
        self.db.add(row)
        self.db.commit()
        return goal

    def get(self, goal_id: str) -> FounderGoal | None:
        row = self.db.get(FounderGoalRow, goal_id)
        return _to_domain(row) if row is not None else None

    def replace(self, goal: FounderGoal) -> FounderGoal:
        row = self.db.get(FounderGoalRow, goal.goal_id)
        if row is None:
            return self.add(goal)
        row.title, row.subtitle, row.updated_at = goal.title, goal.subtitle, goal.updated_at
        self.db.commit()
        return goal

    def list_for_founder(self, founder_id: int) -> tuple[FounderGoal, ...]:
        rows = (
            self.db.query(FounderGoalRow)
            .filter(FounderGoalRow.founder_id == founder_id)
            .order_by(FounderGoalRow.created_at.desc(), FounderGoalRow.goal_id.desc())
            .all()
        )
        return tuple(_to_domain(r) for r in rows)

    def delete(self, goal_id: str) -> None:
        row = self.db.get(FounderGoalRow, goal_id)
        if row is not None:
            self.db.delete(row)
            self.db.commit()
