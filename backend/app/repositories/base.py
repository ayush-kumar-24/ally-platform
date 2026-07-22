"""Generic CRUD repository.

One class that gives every model create/read/update/delete without repeating the
same SQLAlchemy boilerplate in each route. A concrete repository subclasses this
and adds only the queries specific to its model (see founder.py).

Design notes:
- Methods take the `Session` as an argument rather than holding one, so a single
  repository instance is shared across requests and the request-scoped session
  (from get_db) is passed in.
- `commit` is a parameter, default True. Pass commit=False to batch several
  writes into one transaction, or in tests that roll back.
- Writes never invent values the database owns (defaults, triggers); they set
  only what the caller provides, then refresh to return the DB's view.
"""

from typing import Any, Generic, TypeVar

from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session

from app.db.session import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    def __init__(self, model: type[ModelT]):
        self.model = model
        pk = inspect(model).primary_key
        # Single-column PK covers every table here; guard so a composite PK
        # fails loudly rather than silently using the wrong column.
        if len(pk) != 1:
            raise ValueError(f"{model.__name__} has a composite primary key; use get_by() instead of get()")
        self._pk = pk[0]

    # --- read ---

    def get(self, db: Session, id: Any) -> ModelT | None:
        """Fetch by primary key. None if not found."""
        return db.get(self.model, id)

    def get_by(self, db: Session, **filters: Any) -> ModelT | None:
        """Fetch the first row matching equality filters, or None."""
        return db.execute(self._filtered(filters)).scalars().first()

    def list(self, db: Session, *, limit: int = 100, offset: int = 0, **filters: Any) -> list[ModelT]:
        """Fetch rows matching equality filters, paginated."""
        stmt = self._filtered(filters).limit(limit).offset(offset)
        return list(db.execute(stmt).scalars().all())

    def count(self, db: Session, **filters: Any) -> int:
        stmt = select(func.count()).select_from(self.model)
        for field, value in filters.items():
            stmt = stmt.where(getattr(self.model, field) == value)
        return db.execute(stmt).scalar_one()

    # --- write ---

    def create(self, db: Session, data: dict[str, Any], *, commit: bool = True) -> ModelT:
        obj = self.model(**data)
        db.add(obj)
        self._finish(db, obj, commit)
        return obj

    def update(self, db: Session, obj: ModelT, data: dict[str, Any], *, commit: bool = True) -> ModelT:
        """Apply only the provided fields (partial update)."""
        for field, value in data.items():
            setattr(obj, field, value)
        self._finish(db, obj, commit)
        return obj

    def delete(self, db: Session, obj: ModelT, *, commit: bool = True) -> None:
        db.delete(obj)
        if commit:
            db.commit()
        else:
            db.flush()

    # --- internals ---

    def _filtered(self, filters: dict[str, Any]):
        stmt = select(self.model)
        for field, value in filters.items():
            stmt = stmt.where(getattr(self.model, field) == value)
        return stmt

    def _finish(self, db: Session, obj: ModelT, commit: bool) -> None:
        if commit:
            db.commit()
        else:
            db.flush()
        # Pull back DB-owned values (server defaults, trigger-maintained columns).
        db.refresh(obj)
