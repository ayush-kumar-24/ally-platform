"""SQLAlchemy-backed VisionRepository (production).

Maps ORM rows <-> frozen domain models. Untested in the hermetic suite (no
live DB); mirrors the app's other repositories (commit + return the domain
object). Upserts are get-then-add-or-update rather than a native SQL
upsert -- same tradeoff app.founder_goals.db_repository makes, and this
table sees far lower write volume than a hot path would need to justify
the extra complexity.
"""

from __future__ import annotations

from app.vision.db_models import VisionSummaryRow, VisionTerritoryRow
from app.vision.models import VisionSummary, VisionTerritory
from app.vision.repository import VisionRepository


def _territory_to_domain(row: VisionTerritoryRow) -> VisionTerritory:
    return VisionTerritory(
        founder_id=row.founder_id, territory=row.territory, statement=row.statement,
        tag1=row.tag1, tag2=row.tag2, updated_at=row.updated_at,
        image_url=row.image_url,
    )


def _summary_to_domain(row: VisionSummaryRow) -> VisionSummary:
    return VisionSummary(
        founder_id=row.founder_id, target=row.target, current=row.current,
        unit=row.unit, updated_at=row.updated_at,
    )


class SqlAlchemyVisionRepository(VisionRepository):
    def __init__(self, db):
        self.db = db

    def get_territory(self, founder_id: int, territory: str) -> VisionTerritory | None:
        row = self.db.get(VisionTerritoryRow, {"founder_id": founder_id, "territory": territory})
        return _territory_to_domain(row) if row is not None else None

    def list_territories(self, founder_id: int) -> tuple[VisionTerritory, ...]:
        rows = (
            self.db.query(VisionTerritoryRow)
            .filter(VisionTerritoryRow.founder_id == founder_id)
            .order_by(VisionTerritoryRow.territory)
            .all()
        )
        return tuple(_territory_to_domain(r) for r in rows)

    def upsert_territory(self, territory: VisionTerritory) -> VisionTerritory:
        row = self.db.get(VisionTerritoryRow, {"founder_id": territory.founder_id, "territory": territory.territory})
        if row is None:
            row = VisionTerritoryRow(founder_id=territory.founder_id, territory=territory.territory)
            self.db.add(row)
        # Text only. The image columns are deliberately NOT assigned here, so
        # saving a statement never clears a picture the founder attached
        # earlier -- the two are edited independently and arrive on different
        # requests.
        row.statement, row.tag1, row.tag2, row.updated_at = (
            territory.statement, territory.tag1, territory.tag2, territory.updated_at,
        )
        self.db.commit()
        # Read back from the ROW, not the argument. The caller builds its
        # VisionTerritory from the text fields alone, so returning it would
        # report image_url=None on every text save and the page would blank the
        # picture it is still storing.
        return _territory_to_domain(row)

    def set_territory_image(
        self, founder_id: int, territory: str, *, image_url: str | None, storage_path: str | None,
    ) -> VisionTerritory | None:
        """Attach or clear one territory's picture, leaving its text alone.

        Returns None when the territory row does not exist yet: an image cannot
        be hung on a vision the founder has not written, and silently creating
        an empty statement row to hold one would put a blank card on their
        page.
        """
        row = self.db.get(VisionTerritoryRow, {"founder_id": founder_id, "territory": territory})
        if row is None:
            return None
        row.image_url = image_url
        row.image_storage_path = storage_path
        self.db.commit()
        return _territory_to_domain(row)

    def get_territory_storage_path(self, founder_id: int, territory: str) -> str | None:
        """Where the current picture lives, for deleting it when it is replaced."""
        row = self.db.get(VisionTerritoryRow, {"founder_id": founder_id, "territory": territory})
        return row.image_storage_path if row is not None else None

    def get_summary(self, founder_id: int) -> VisionSummary | None:
        row = self.db.get(VisionSummaryRow, founder_id)
        return _summary_to_domain(row) if row is not None else None

    def upsert_summary(self, summary: VisionSummary) -> VisionSummary:
        row = self.db.get(VisionSummaryRow, summary.founder_id)
        if row is None:
            row = VisionSummaryRow(founder_id=summary.founder_id)
            self.db.add(row)
        row.target, row.current, row.unit, row.updated_at = (
            summary.target, summary.current, summary.unit, summary.updated_at,
        )
        self.db.commit()
        return summary
