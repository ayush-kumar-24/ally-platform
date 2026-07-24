from sqlalchemy.orm import Session

from app.models.schema import DiscoveryCalls
from app.repositories.base import BaseRepository


class DiscoveryCallRepository(BaseRepository[DiscoveryCalls]):
    def __init__(self) -> None:
        super().__init__(DiscoveryCalls)

    def list_for_founder(self, db: Session, founder_id: int) -> list[DiscoveryCalls]:
        return self.list(db, founder_id=founder_id, limit=200)


discovery_call_repository = DiscoveryCallRepository()
