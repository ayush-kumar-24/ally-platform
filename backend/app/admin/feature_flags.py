"""Feature flags -- global defaults with per-founder overrides.

Resolution order, most specific wins:

    per-founder override  ->  global flag  ->  `default` argument  ->  False

Fails closed: an unknown flag is off. That matters because flags gate things like
"enable beta features" — if a typo in a flag name silently returned True, the typo
would ship the feature to everyone, which is the opposite of what a kill switch is
for. A flag you cannot find is a flag you have not turned on.

Kill switches (e.g. "disable_claude") should be modelled as an *enable* flag that is
on by default in code and turned off here, so the stored state reads the same way
round as the question being asked.
"""

from __future__ import annotations

import abc
import threading
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


@dataclass(frozen=True)
class FeatureFlag:
    key: str
    enabled: bool
    description: str = ""
    updated_by: int | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class FlagOverride:
    key: str
    founder_id: int
    enabled: bool
    updated_by: int | None = None
    updated_at: datetime | None = None


class FeatureFlagRow(Base):
    __tablename__ = "feature_flags"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    updated_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())


class FeatureFlagOverrideRow(Base):
    __tablename__ = "feature_flag_overrides"

    key: Mapped[str] = mapped_column(
        String(60), ForeignKey("feature_flags.key", ondelete="CASCADE"), primary_key=True)
    founder_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("founders.founder_id", ondelete="CASCADE"), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    updated_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())


class FeatureFlagRepository(abc.ABC):
    @abc.abstractmethod
    def list_flags(self) -> list[FeatureFlag]: ...

    @abc.abstractmethod
    def get_flag(self, key: str) -> FeatureFlag | None: ...

    @abc.abstractmethod
    def set_flag(self, key: str, *, enabled: bool, description: str,
                 admin_id: int | None, at: datetime) -> FeatureFlag: ...

    @abc.abstractmethod
    def set_override(self, key: str, founder_id: int, *, enabled: bool | None,
                     admin_id: int | None, at: datetime) -> None:
        """`enabled=None` clears the override so the founder falls back to global."""

    @abc.abstractmethod
    def get_override(self, key: str, founder_id: int) -> FlagOverride | None: ...

    @abc.abstractmethod
    def list_overrides(self, founder_id: int) -> list[FlagOverride]: ...


class InMemoryFeatureFlagRepository(FeatureFlagRepository):
    def __init__(self, flags: dict[str, bool] | None = None) -> None:
        self._flags: dict[str, FeatureFlag] = {
            k: FeatureFlag(key=k, enabled=v) for k, v in (flags or {}).items()}
        self._overrides: dict[tuple[str, int], FlagOverride] = {}
        self._lock = threading.RLock()

    def list_flags(self) -> list[FeatureFlag]:
        with self._lock:
            return sorted(self._flags.values(), key=lambda f: f.key)

    def get_flag(self, key: str) -> FeatureFlag | None:
        with self._lock:
            return self._flags.get(key)

    def set_flag(self, key, *, enabled, description, admin_id, at) -> FeatureFlag:
        with self._lock:
            flag = FeatureFlag(key=key, enabled=enabled, description=description,
                               updated_by=admin_id, updated_at=at)
            self._flags[key] = flag
            return flag

    def set_override(self, key, founder_id, *, enabled, admin_id, at) -> None:
        with self._lock:
            if enabled is None:
                self._overrides.pop((key, founder_id), None)
            else:
                self._overrides[(key, founder_id)] = FlagOverride(
                    key=key, founder_id=founder_id, enabled=enabled,
                    updated_by=admin_id, updated_at=at)

    def get_override(self, key, founder_id) -> FlagOverride | None:
        with self._lock:
            return self._overrides.get((key, founder_id))

    def list_overrides(self, founder_id) -> list[FlagOverride]:
        with self._lock:
            return [o for (_, fid), o in self._overrides.items() if fid == founder_id]


class SqlAlchemyFeatureFlagRepository(FeatureFlagRepository):
    def __init__(self, db):
        self.db = db

    def _safe(self, fn, fallback):
        """Flag tables arrive with a pending migration. Until then every flag reads
        as absent, which the resolver already treats as OFF -- so degrading here
        fails closed rather than accidentally enabling anything."""
        try:
            return fn()
        except Exception:
            self.db.rollback()
            return fallback

    def list_flags(self) -> list[FeatureFlag]:
        return self._safe(lambda: [_flag(r) for r in
                self.db.query(FeatureFlagRow).order_by(FeatureFlagRow.key).all()], [])

    def get_flag(self, key: str) -> FeatureFlag | None:
        row = self._safe(lambda: self.db.get(FeatureFlagRow, key), None)
        return _flag(row) if row else None

    def set_flag(self, key, *, enabled, description, admin_id, at) -> FeatureFlag:
        row = self.db.get(FeatureFlagRow, key)
        if row is None:
            row = FeatureFlagRow(key=key)
            self.db.add(row)
        row.enabled, row.description = enabled, description
        row.updated_by, row.updated_at = admin_id, at
        self.db.commit()
        self.db.refresh(row)
        return _flag(row)

    def set_override(self, key, founder_id, *, enabled, admin_id, at) -> None:
        row = self.db.get(FeatureFlagOverrideRow, {"key": key, "founder_id": founder_id})
        if enabled is None:
            if row is not None:
                self.db.delete(row)
                self.db.commit()
            return
        if row is None:
            row = FeatureFlagOverrideRow(key=key, founder_id=founder_id)
            self.db.add(row)
        row.enabled, row.updated_by, row.updated_at = enabled, admin_id, at
        self.db.commit()

    def get_override(self, key, founder_id) -> FlagOverride | None:
        row = self._safe(lambda: self.db.get(
            FeatureFlagOverrideRow, {"key": key, "founder_id": founder_id}), None)
        return _override(row) if row else None

    def list_overrides(self, founder_id) -> list[FlagOverride]:
        rows = self._safe(lambda: (self.db.query(FeatureFlagOverrideRow)
                .filter(FeatureFlagOverrideRow.founder_id == founder_id).all()), [])
        return [_override(r) for r in rows]


def _flag(r) -> FeatureFlag:
    return FeatureFlag(key=r.key, enabled=r.enabled, description=r.description or "",
                       updated_by=r.updated_by, updated_at=r.updated_at)


def _override(r) -> FlagOverride:
    return FlagOverride(key=r.key, founder_id=r.founder_id, enabled=r.enabled,
                        updated_by=r.updated_by, updated_at=r.updated_at)


class FeatureFlagService:
    def __init__(self, repository: FeatureFlagRepository, *, clock=None):
        self.repository = repository
        self._now = clock or (lambda: datetime.now(timezone.utc))

    def is_enabled(self, key: str, founder_id: int | None = None, *,
                   default: bool = False) -> bool:
        """Resolve a flag. Per-founder override beats the global value."""
        if founder_id is not None:
            override = self.repository.get_override(key, founder_id)
            if override is not None:
                return override.enabled
        flag = self.repository.get_flag(key)
        return flag.enabled if flag is not None else default

    def list_flags(self) -> list[FeatureFlag]:
        return self.repository.list_flags()

    def set_flag(self, key: str, *, enabled: bool, description: str = "",
                 admin_id: int | None = None) -> FeatureFlag:
        return self.repository.set_flag(key, enabled=enabled, description=description,
                                        admin_id=admin_id, at=self._now())

    def set_override(self, key: str, founder_id: int, *, enabled: bool | None,
                     admin_id: int | None = None) -> None:
        self.repository.set_override(key, founder_id, enabled=enabled,
                                     admin_id=admin_id, at=self._now())

    def flags_for_founder(self, founder_id: int) -> dict[str, bool]:
        """Every known flag resolved for one founder -- what the app should see."""
        overrides = {o.key: o.enabled for o in self.repository.list_overrides(founder_id)}
        return {f.key: overrides.get(f.key, f.enabled) for f in self.repository.list_flags()}


def build_feature_flag_service(repository: FeatureFlagRepository | None = None, *,
                               clock=None) -> FeatureFlagService:
    return FeatureFlagService(repository or InMemoryFeatureFlagRepository(), clock=clock)
