"""Beta access -- a waitlist that remembers who it passed over.

The problem this solves: 200 founders want in, a slot holds 100. Picking 100 is
easy. What is hard, and what a spreadsheet always gets wrong, is the other 100 --
they have to be *first* next time, and somebody has to be able to prove they were.

So the waitlist is a queue with memory. Every release does two things, not one:

    the picked           ->  status `invited`, invite email queued
    everyone still waiting ->  times_deferred + 1, "still on the list" email queued

and `next_up` orders by that counter:

    ORDER BY times_deferred DESC, priority DESC, joined_at ASC

Read left to right that is: whoever has been passed over most goes first; ties
break on an admin's manual bump; ties after that break on who joined earliest.
Nobody can be skipped twice while a later signup gets in ahead of them, because
being skipped is the thing that moves you up. `priority` exists for the founder
you genuinely do want to jump the queue (an investor's referral, a design
partner) -- it is a deliberate, audited override rather than a quiet re-sort.

Two states, not one, between "waiting" and "invited"
---------------------------------------------------
Selection (`select`) and release (`release`) are separate steps. Selection is
reviewable and reversible -- you stage 100 people into an open cohort, look at the
list, swap a few. Release is the irreversible half: it sends mail. Merging them
would mean the first click of the wrong button emails 200 founders.

Email is a durable queue, not a side effect
-------------------------------------------
`release` never sends anything. It queues (`email_state = 'pending'`) and returns.
`dispatch_pending` drains the queue and records `sent` / `failed` per entry, so a
provider outage halfway through 200 messages is a retry rather than a mystery --
and re-running it can never double-send, because only pending and failed rows are
picked up.
"""

from __future__ import annotations

import abc
import re
import threading
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.admin.errors import AdminError
from app.db.session import Base

MAX_SLOT_SIZE = 5000
MAX_NAME = 120

#: Deliberately loose. This is not RFC 5322 -- the only address that is genuinely
#: verified is one that receives mail, which is what the invite itself does. The
#: check exists to catch a paste that is obviously not an address (a name, a blank
#: line, a stray comma) before it becomes a permanent row.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _looks_like_email(value: str) -> bool:
    return bool(value) and len(value) <= 200 and bool(_EMAIL_RE.match(value))


class BetaError(AdminError):
    """Base for beta-access failures."""


class InvalidCohortError(BetaError):
    def __init__(self, reason: str):
        super().__init__(f"Invalid cohort: {reason}.", status_code=422)


class CohortNotFoundError(BetaError):
    def __init__(self, cohort_id: str):
        super().__init__(f"Cohort '{cohort_id}' was not found.", status_code=404)


class CohortClosedError(BetaError):
    """The cohort has already been released; its invites are out."""

    def __init__(self, cohort_id: str):
        super().__init__(
            f"Cohort '{cohort_id}' has already been released and cannot be changed.",
            status_code=409)


class SlotFullError(BetaError):
    def __init__(self, slot_size: int, requested: int):
        super().__init__(
            f"This cohort holds {slot_size}; {requested} were selected.", status_code=422)


class InvalidWaitlistEntryError(BetaError):
    def __init__(self, reason: str):
        super().__init__(f"Invalid waitlist entry: {reason}.", status_code=422)


class EntryNotFoundError(BetaError):
    def __init__(self, entry_id: str):
        super().__init__(f"Waitlist entry '{entry_id}' was not found.", status_code=404)


class EntryStatus(str, Enum):
    #: On the list, not yet picked.
    WAITING = "waiting"
    #: Staged into an open cohort. No mail sent yet -- still reversible.
    SELECTED = "selected"
    #: Cohort released; the invite is queued or out.
    INVITED = "invited"
    #: They took the invite up (signed in as a founder after being invited).
    ACCEPTED = "accepted"
    #: They said no. Distinct from REMOVED: this was their decision.
    DECLINED = "declined"
    #: Taken off the list by an admin (bounced address, spam signup).
    REMOVED = "removed"


class EmailKind(str, Enum):
    INVITE = "invite"
    DEFERRED = "deferred"


class EmailState(str, Enum):
    #: Nothing owed to this founder right now.
    NONE = "none"
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"
    #: Deliberately not sent -- this deployment has no SMTP configured. Distinct
    #: from SENT (a lie) and from FAILED (which invites a pointless retry).
    SKIPPED = "skipped"


class CohortStatus(str, Enum):
    OPEN = "open"
    RELEASED = "released"


@dataclass(frozen=True)
class WaitlistEntry:
    entry_id: str
    email: str
    joined_at: datetime
    full_name: str = ""
    founder_id: int | None = None
    status: EntryStatus = EntryStatus.WAITING
    source: str = "signup"
    #: How many releases have passed this founder over. The queue's memory.
    times_deferred: int = 0
    #: Manual bump. Higher goes first, after times_deferred.
    priority: int = 0
    cohort_id: str | None = None
    invited_at: datetime | None = None
    responded_at: datetime | None = None
    coupon_code: str | None = None
    email_kind: EmailKind | None = None
    email_state: EmailState = EmailState.NONE
    email_error: str | None = None
    email_sent_at: datetime | None = None
    notes: str = ""


@dataclass(frozen=True)
class Cohort:
    cohort_id: str
    name: str
    slot_size: int
    created_at: datetime
    status: CohortStatus = CohortStatus.OPEN
    #: Coupon handed to everyone invited in this cohort. Validated when set.
    coupon_code: str | None = None
    #: Whether the founders who were passed over hear about it.
    notify_deferred: bool = True
    created_by: int | None = None
    released_at: datetime | None = None
    invited_count: int = 0
    deferred_count: int = 0


@dataclass(frozen=True)
class ReleaseResult:
    cohort: Cohort
    invited: int
    deferred: int
    #: Entry ids whose invite mail is queued -- what `dispatch_pending` will pick up.
    queued_emails: int


@dataclass(frozen=True)
class DispatchResult:
    sent: int = 0
    failed: int = 0
    #: Not attempted because the deployment has no mail configured.
    skipped: int = 0
    #: Addresses that failed, so an admin sees who to chase rather than a count.
    failures: list[str] = field(default_factory=list)


# --- storage ----------------------------------------------------------------

class WaitlistEntryRow(Base):
    __tablename__ = "beta_waitlist_entries"

    entry_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(200), nullable=False, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False, server_default="")
    founder_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("founders.founder_id", ondelete="SET NULL"),
        nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False,
                                        server_default="waiting", index=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False, server_default="signup")
    times_deferred: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    cohort_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("beta_cohorts.cohort_id", ondelete="SET NULL"),
        nullable=True, index=True)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())
    invited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    coupon_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    email_kind: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email_state: Mapped[str] = mapped_column(String(20), nullable=False,
                                             server_default="none", index=True)
    email_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    email_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, server_default="")


class CohortRow(Base):
    __tablename__ = "beta_cohorts"

    cohort_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slot_size: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="open")
    coupon_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    notify_deferred: Mapped[bool] = mapped_column(Boolean, nullable=False,
                                                  server_default="true")
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invited_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    deferred_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")


class BetaRepository(abc.ABC):
    # -- entries ------------------------------------------------------------
    @abc.abstractmethod
    def get_entry(self, entry_id: str) -> WaitlistEntry | None: ...

    @abc.abstractmethod
    def get_entry_by_email(self, email: str) -> WaitlistEntry | None: ...

    @abc.abstractmethod
    def add_entry(self, entry: WaitlistEntry) -> WaitlistEntry: ...

    @abc.abstractmethod
    def update_entry(self, entry_id: str, **changes) -> WaitlistEntry | None: ...

    @abc.abstractmethod
    def list_entries(self, *, status: EntryStatus | None = None, search: str | None = None,
                     cohort_id: str | None = None, limit: int = 100,
                     offset: int = 0) -> tuple[list[WaitlistEntry], int]: ...

    @abc.abstractmethod
    def next_up(self, limit: int) -> list[WaitlistEntry]:
        """Waiting entries in queue order: most-deferred first."""

    @abc.abstractmethod
    def counts_by_status(self) -> dict[str, int]: ...

    @abc.abstractmethod
    def defer_all_waiting(self, *, at: datetime, queue_email: bool) -> int:
        """+1 to times_deferred for every WAITING entry. Returns how many moved."""

    @abc.abstractmethod
    def pending_emails(self, limit: int) -> list[WaitlistEntry]:
        """Entries owed mail -- queued, or failed and awaiting a retry."""

    # -- cohorts ------------------------------------------------------------
    @abc.abstractmethod
    def create_cohort(self, cohort: Cohort) -> Cohort: ...

    @abc.abstractmethod
    def get_cohort(self, cohort_id: str) -> Cohort | None: ...

    @abc.abstractmethod
    def update_cohort(self, cohort_id: str, **changes) -> Cohort | None: ...

    @abc.abstractmethod
    def list_cohorts(self, *, limit: int = 50,
                     offset: int = 0) -> tuple[list[Cohort], int]: ...


def _queue_key(e: WaitlistEntry) -> tuple:
    """The queue order, in one place so memory and SQL cannot drift apart.

    Negated where the SQL is DESC: most-deferred first, then the manual bump, then
    oldest signup, then entry_id purely so the order is total and stable.
    """
    return (-e.times_deferred, -e.priority, e.joined_at, e.entry_id)


class InMemoryBetaRepository(BetaRepository):
    def __init__(self, entries: list[WaitlistEntry] | None = None) -> None:
        self._entries: dict[str, WaitlistEntry] = {e.entry_id: e for e in (entries or [])}
        self._cohorts: dict[str, Cohort] = {}
        self._lock = threading.RLock()

    def get_entry(self, entry_id: str) -> WaitlistEntry | None:
        with self._lock:
            return self._entries.get(entry_id)

    def get_entry_by_email(self, email: str) -> WaitlistEntry | None:
        with self._lock:
            return next((e for e in self._entries.values() if e.email == email), None)

    def add_entry(self, entry: WaitlistEntry) -> WaitlistEntry:
        with self._lock:
            self._entries[entry.entry_id] = entry
            return entry

    def update_entry(self, entry_id: str, **changes) -> WaitlistEntry | None:
        with self._lock:
            existing = self._entries.get(entry_id)
            if existing is None:
                return None
            updated = replace(existing, **changes)
            self._entries[entry_id] = updated
            return updated

    def list_entries(self, *, status=None, search=None, cohort_id=None, limit=100, offset=0):
        with self._lock:
            rows = list(self._entries.values())
        if status is not None:
            rows = [e for e in rows if e.status is status]
        if cohort_id is not None:
            rows = [e for e in rows if e.cohort_id == cohort_id]
        if search:
            needle = search.strip().lower()
            rows = [e for e in rows
                    if needle in e.email.lower() or needle in (e.full_name or "").lower()]
        rows.sort(key=_queue_key)
        return rows[offset:offset + limit], len(rows)

    def next_up(self, limit: int) -> list[WaitlistEntry]:
        with self._lock:
            rows = [e for e in self._entries.values() if e.status is EntryStatus.WAITING]
        rows.sort(key=_queue_key)
        return rows[:limit]

    def counts_by_status(self) -> dict[str, int]:
        with self._lock:
            rows = list(self._entries.values())
        out: dict[str, int] = {}
        for e in rows:
            out[e.status.value] = out.get(e.status.value, 0) + 1
        return out

    def defer_all_waiting(self, *, at: datetime, queue_email: bool) -> int:
        with self._lock:
            moved = 0
            for entry_id, e in list(self._entries.items()):
                if e.status is not EntryStatus.WAITING:
                    continue
                self._entries[entry_id] = replace(
                    e,
                    times_deferred=e.times_deferred + 1,
                    email_kind=EmailKind.DEFERRED if queue_email else e.email_kind,
                    email_state=EmailState.QUEUED if queue_email else e.email_state,
                    email_error=None if queue_email else e.email_error)
                moved += 1
            return moved

    def pending_emails(self, limit: int) -> list[WaitlistEntry]:
        with self._lock:
            rows = [e for e in self._entries.values()
                    if e.email_state in (EmailState.QUEUED, EmailState.FAILED)
                    and e.email_kind is not None]
        rows.sort(key=lambda e: (e.email_state is not EmailState.QUEUED, e.joined_at))
        return rows[:limit]

    def create_cohort(self, cohort: Cohort) -> Cohort:
        with self._lock:
            self._cohorts[cohort.cohort_id] = cohort
            return cohort

    def get_cohort(self, cohort_id: str) -> Cohort | None:
        with self._lock:
            return self._cohorts.get(cohort_id)

    def update_cohort(self, cohort_id: str, **changes) -> Cohort | None:
        with self._lock:
            existing = self._cohorts.get(cohort_id)
            if existing is None:
                return None
            updated = replace(existing, **changes)
            self._cohorts[cohort_id] = updated
            return updated

    def list_cohorts(self, *, limit=50, offset=0):
        with self._lock:
            rows = sorted(self._cohorts.values(),
                          key=lambda c: (c.created_at, c.cohort_id), reverse=True)
        return rows[offset:offset + limit], len(rows)


class SqlAlchemyBetaRepository(BetaRepository):
    def __init__(self, db):
        self.db = db

    # -- entries ------------------------------------------------------------

    def get_entry(self, entry_id: str) -> WaitlistEntry | None:
        row = self.db.get(WaitlistEntryRow, entry_id)
        return _to_entry(row) if row else None

    def get_entry_by_email(self, email: str) -> WaitlistEntry | None:
        row = (self.db.query(WaitlistEntryRow)
                   .filter(WaitlistEntryRow.email == email).first())
        return _to_entry(row) if row else None

    def add_entry(self, entry: WaitlistEntry) -> WaitlistEntry:
        self.db.add(WaitlistEntryRow(
            entry_id=entry.entry_id, email=entry.email, full_name=entry.full_name,
            founder_id=entry.founder_id, status=entry.status.value, source=entry.source,
            times_deferred=entry.times_deferred, priority=entry.priority,
            cohort_id=entry.cohort_id, joined_at=entry.joined_at,
            invited_at=entry.invited_at, responded_at=entry.responded_at,
            coupon_code=entry.coupon_code,
            email_kind=entry.email_kind.value if entry.email_kind else None,
            email_state=entry.email_state.value, email_error=entry.email_error,
            email_sent_at=entry.email_sent_at, notes=entry.notes))
        self.db.commit()
        return entry

    def update_entry(self, entry_id: str, **changes) -> WaitlistEntry | None:
        row = self.db.get(WaitlistEntryRow, entry_id)
        if row is None:
            return None
        for key, value in changes.items():
            setattr(row, key, value.value if isinstance(value, Enum) else value)
        self.db.commit()
        return _to_entry(row)

    def _ordered(self, q):
        return q.order_by(WaitlistEntryRow.times_deferred.desc(),
                          WaitlistEntryRow.priority.desc(),
                          WaitlistEntryRow.joined_at.asc(),
                          WaitlistEntryRow.entry_id.asc())

    def list_entries(self, *, status=None, search=None, cohort_id=None, limit=100, offset=0):
        q = self.db.query(WaitlistEntryRow)
        if status is not None:
            q = q.filter(WaitlistEntryRow.status == status.value)
        if cohort_id is not None:
            q = q.filter(WaitlistEntryRow.cohort_id == cohort_id)
        if search:
            like = f"%{search.strip().lower()}%"
            q = q.filter(func.lower(WaitlistEntryRow.email).like(like)
                         | func.lower(WaitlistEntryRow.full_name).like(like))
        total = q.count()
        rows = self._ordered(q).limit(limit).offset(offset).all()
        return [_to_entry(r) for r in rows], total

    def next_up(self, limit: int) -> list[WaitlistEntry]:
        q = self.db.query(WaitlistEntryRow).filter(
            WaitlistEntryRow.status == EntryStatus.WAITING.value)
        return [_to_entry(r) for r in self._ordered(q).limit(limit).all()]

    def counts_by_status(self) -> dict[str, int]:
        rows = (self.db.query(WaitlistEntryRow.status, func.count())
                    .group_by(WaitlistEntryRow.status).all())
        return {status: count for status, count in rows}

    def defer_all_waiting(self, *, at: datetime, queue_email: bool) -> int:
        changes = {WaitlistEntryRow.times_deferred: WaitlistEntryRow.times_deferred + 1}
        if queue_email:
            changes[WaitlistEntryRow.email_kind] = EmailKind.DEFERRED.value
            changes[WaitlistEntryRow.email_state] = EmailState.QUEUED.value
            changes[WaitlistEntryRow.email_error] = None
        moved = (self.db.query(WaitlistEntryRow)
                     .filter(WaitlistEntryRow.status == EntryStatus.WAITING.value)
                     .update(changes, synchronize_session=False))
        self.db.commit()
        return moved

    def pending_emails(self, limit: int) -> list[WaitlistEntry]:
        rows = (self.db.query(WaitlistEntryRow)
                    .filter(WaitlistEntryRow.email_kind.isnot(None))
                    .filter(WaitlistEntryRow.email_state.in_(
                        (EmailState.QUEUED.value, EmailState.FAILED.value)))
                    # Queued before failed: a first attempt outranks a retry.
                    .order_by(WaitlistEntryRow.email_state.asc(),
                              WaitlistEntryRow.joined_at.asc())
                    .limit(limit).all())
        return [_to_entry(r) for r in rows]

    # -- cohorts ------------------------------------------------------------

    def create_cohort(self, cohort: Cohort) -> Cohort:
        self.db.add(CohortRow(
            cohort_id=cohort.cohort_id, name=cohort.name, slot_size=cohort.slot_size,
            status=cohort.status.value, coupon_code=cohort.coupon_code,
            notify_deferred=cohort.notify_deferred, created_by=cohort.created_by,
            created_at=cohort.created_at, released_at=cohort.released_at,
            invited_count=cohort.invited_count, deferred_count=cohort.deferred_count))
        self.db.commit()
        return cohort

    def get_cohort(self, cohort_id: str) -> Cohort | None:
        row = self.db.get(CohortRow, cohort_id)
        return _to_cohort(row) if row else None

    def update_cohort(self, cohort_id: str, **changes) -> Cohort | None:
        row = self.db.get(CohortRow, cohort_id)
        if row is None:
            return None
        for key, value in changes.items():
            setattr(row, key, value.value if isinstance(value, Enum) else value)
        self.db.commit()
        return _to_cohort(row)

    def list_cohorts(self, *, limit=50, offset=0):
        q = self.db.query(CohortRow)
        total = q.count()
        rows = (q.order_by(CohortRow.created_at.desc(), CohortRow.cohort_id.desc())
                 .limit(limit).offset(offset).all())
        return [_to_cohort(r) for r in rows], total


def _to_entry(row: WaitlistEntryRow) -> WaitlistEntry:
    return WaitlistEntry(
        entry_id=row.entry_id, email=row.email, full_name=row.full_name or "",
        founder_id=row.founder_id, status=EntryStatus(row.status), source=row.source,
        times_deferred=row.times_deferred, priority=row.priority, cohort_id=row.cohort_id,
        joined_at=row.joined_at, invited_at=row.invited_at, responded_at=row.responded_at,
        coupon_code=row.coupon_code,
        email_kind=EmailKind(row.email_kind) if row.email_kind else None,
        email_state=EmailState(row.email_state), email_error=row.email_error,
        email_sent_at=row.email_sent_at, notes=row.notes or "")


def _to_cohort(row: CohortRow) -> Cohort:
    return Cohort(
        cohort_id=row.cohort_id, name=row.name, slot_size=row.slot_size,
        status=CohortStatus(row.status), coupon_code=row.coupon_code,
        notify_deferred=row.notify_deferred, created_by=row.created_by,
        created_at=row.created_at, released_at=row.released_at,
        invited_count=row.invited_count, deferred_count=row.deferred_count)


# --- service ----------------------------------------------------------------

class BetaAccessService:
    """The waitlist, the cohorts, and the queue that connects them.

    `sender` is injected rather than imported so tests -- and a dry run -- can
    exercise the whole release path without a mail server. It takes
    (entry, kind, cohort) and returns (sent, error): a False with no error means
    the deployment has no SMTP configured, which is not a failure to retry.
    """

    def __init__(self, repository: BetaRepository, *, sender=None, coupons=None,
                 clock=None, id_factory=None):
        self.repository = repository
        self.coupons = coupons
        self._send = sender
        self._now = clock or (lambda: datetime.now(timezone.utc))
        self._new_id = id_factory or (lambda: uuid.uuid4().hex)

    # -- joining ------------------------------------------------------------

    def join(self, *, email: str, full_name: str = "", source: str = "signup",
             founder_id: int | None = None) -> tuple[WaitlistEntry, bool]:
        """Idempotent. Returns (entry, created).

        Signing up twice must not reset your place -- the second attempt returns
        the original entry untouched, which is also what stops a refresh-happy
        founder from clearing their own accumulated `times_deferred`.
        """
        email = (email or "").strip().lower()
        if not _looks_like_email(email):
            raise InvalidWaitlistEntryError("a valid email address is required")
        full_name = (full_name or "").strip()[:MAX_NAME]

        existing = self.repository.get_entry_by_email(email)
        if existing is not None:
            # Late-binding the founder id: they joined by email, then signed up.
            if founder_id is not None and existing.founder_id is None:
                existing = self.repository.update_entry(
                    existing.entry_id, founder_id=founder_id) or existing
            return existing, False

        return self.repository.add_entry(WaitlistEntry(
            entry_id=self._new_id(), email=email, full_name=full_name,
            founder_id=founder_id, source=source[:40] or "signup",
            joined_at=self._now())), True

    def list_entries(self, *, status: EntryStatus | None = None, search: str | None = None,
                     cohort_id: str | None = None, limit: int = 100,
                     offset: int = 0) -> tuple[list[WaitlistEntry], int]:
        return self.repository.list_entries(status=status, search=search,
                                            cohort_id=cohort_id, limit=limit, offset=offset)

    def next_up(self, limit: int = 100) -> list[WaitlistEntry]:
        """Who the next release would take, in order. The preview behind the
        "auto-pick" button -- an admin sees the list before it becomes 100 emails."""
        return self.repository.next_up(max(1, min(limit, MAX_SLOT_SIZE)))

    def stats(self) -> dict[str, int]:
        counts = self.repository.counts_by_status()
        return {status.value: counts.get(status.value, 0) for status in EntryStatus}

    def set_priority(self, entry_id: str, priority: int) -> WaitlistEntry:
        entry = self.repository.update_entry(entry_id, priority=int(priority))
        if entry is None:
            raise EntryNotFoundError(entry_id)
        return entry

    def set_status(self, entry_id: str, status: EntryStatus) -> WaitlistEntry:
        changes: dict = {"status": status}
        if status in (EntryStatus.ACCEPTED, EntryStatus.DECLINED):
            changes["responded_at"] = self._now()
        entry = self.repository.update_entry(entry_id, **changes)
        if entry is None:
            raise EntryNotFoundError(entry_id)
        return entry

    # -- cohorts ------------------------------------------------------------

    def create_cohort(self, *, name: str, slot_size: int, coupon_code: str | None = None,
                      notify_deferred: bool = True, admin_id: int | None = None) -> Cohort:
        name = (name or "").strip()
        if not name:
            raise InvalidCohortError("a name is required")
        if len(name) > MAX_NAME:
            raise InvalidCohortError(f"the name may not exceed {MAX_NAME} characters")
        if slot_size < 1 or slot_size > MAX_SLOT_SIZE:
            raise InvalidCohortError(f"slot size must be between 1 and {MAX_SLOT_SIZE}")

        coupon_code = self._resolve_coupon(coupon_code)
        return self.repository.create_cohort(Cohort(
            cohort_id=self._new_id(), name=name, slot_size=slot_size,
            coupon_code=coupon_code, notify_deferred=notify_deferred,
            created_by=admin_id, created_at=self._now()))

    def _resolve_coupon(self, code: str | None) -> str | None:
        """Reject an unknown or inactive code at cohort-creation time.

        The alternative is discovering it in 100 invite emails that quote a code
        the checkout will refuse -- which is worse than not offering one at all.
        """
        if not code or not code.strip():
            return None
        code = code.strip().upper()
        if self.coupons is None:
            return code
        coupon = self.coupons.get(code)
        if coupon is None:
            raise InvalidCohortError(f"coupon '{code}' does not exist")
        if not coupon.active:
            raise InvalidCohortError(f"coupon '{code}' is not active")
        if coupon.expires_at and coupon.expires_at <= self._now():
            raise InvalidCohortError(f"coupon '{code}' has expired")
        return code

    def get_cohort(self, cohort_id: str) -> Cohort:
        cohort = self.repository.get_cohort(cohort_id)
        if cohort is None:
            raise CohortNotFoundError(cohort_id)
        return cohort

    def list_cohorts(self, *, limit: int = 50, offset: int = 0) -> tuple[list[Cohort], int]:
        return self.repository.list_cohorts(limit=limit, offset=offset)

    def select(self, cohort_id: str, *, entry_ids: list[str] | None = None,
               auto_count: int | None = None) -> list[WaitlistEntry]:
        """Stage entries into an open cohort. Sends nothing.

        Either an explicit list of entry ids, or `auto_count` to take the top N off
        the queue. Re-selecting replaces the previous staging, so an admin can fix a
        mistake before release without a separate "unselect" step.
        """
        cohort = self.get_cohort(cohort_id)
        if cohort.status is not CohortStatus.OPEN:
            raise CohortClosedError(cohort_id)
        if (entry_ids is None) == (auto_count is None):
            raise InvalidCohortError("provide either entry_ids or auto_count, not both")

        if auto_count is not None:
            if auto_count < 1:
                raise InvalidCohortError("auto_count must be at least 1")
            chosen = self.repository.next_up(min(auto_count, cohort.slot_size))
        else:
            chosen = []
            seen: set[str] = set()
            for entry_id in entry_ids:
                if entry_id in seen:
                    continue
                seen.add(entry_id)
                entry = self.repository.get_entry(entry_id)
                if entry is None:
                    raise EntryNotFoundError(entry_id)
                if entry.status not in (EntryStatus.WAITING, EntryStatus.SELECTED):
                    raise InvalidCohortError(
                        f"{entry.email} is '{entry.status.value}' and cannot be selected")
                chosen.append(entry)

        if len(chosen) > cohort.slot_size:
            raise SlotFullError(cohort.slot_size, len(chosen))

        # Clear the previous staging first so a re-select is a replacement rather
        # than an addition -- otherwise a corrected list would silently union with
        # the wrong one and overshoot the slot.
        keep = {e.entry_id for e in chosen}
        staged, _ = self.repository.list_entries(
            status=EntryStatus.SELECTED, cohort_id=cohort_id, limit=MAX_SLOT_SIZE)
        for entry in staged:
            if entry.entry_id not in keep:
                self.repository.update_entry(
                    entry.entry_id, status=EntryStatus.WAITING, cohort_id=None)

        return [self.repository.update_entry(
            e.entry_id, status=EntryStatus.SELECTED, cohort_id=cohort_id) for e in chosen]

    def release(self, cohort_id: str) -> ReleaseResult:
        """The irreversible half: invite the selected, defer everyone else, queue mail.

        Order matters. The selected are moved OUT of `waiting` before the bulk
        deferral runs, so nobody is both invited and deferred by the same release.
        """
        cohort = self.get_cohort(cohort_id)
        if cohort.status is not CohortStatus.OPEN:
            raise CohortClosedError(cohort_id)

        selected, _ = self.repository.list_entries(
            status=EntryStatus.SELECTED, cohort_id=cohort_id, limit=MAX_SLOT_SIZE)
        if not selected:
            raise InvalidCohortError("no one has been selected into this cohort yet")

        at = self._now()
        for entry in selected:
            self.repository.update_entry(
                entry.entry_id, status=EntryStatus.INVITED, invited_at=at,
                coupon_code=cohort.coupon_code, email_kind=EmailKind.INVITE,
                email_state=EmailState.QUEUED, email_error=None)

        deferred = self.repository.defer_all_waiting(
            at=at, queue_email=cohort.notify_deferred)

        released = self.repository.update_cohort(
            cohort_id, status=CohortStatus.RELEASED, released_at=at,
            invited_count=len(selected), deferred_count=deferred)

        queued = len(selected) + (deferred if cohort.notify_deferred else 0)
        return ReleaseResult(cohort=released or cohort, invited=len(selected),
                             deferred=deferred, queued_emails=queued)

    # -- mail ---------------------------------------------------------------

    def queue_invite(self, entry_id: str) -> WaitlistEntry:
        """Re-queue one invite -- the "resend" button, and the fix for a bounce."""
        entry = self.repository.get_entry(entry_id)
        if entry is None:
            raise EntryNotFoundError(entry_id)
        if entry.status is not EntryStatus.INVITED:
            raise InvalidCohortError(
                f"{entry.email} has not been invited, so there is no invite to resend")
        return self.repository.update_entry(
            entry_id, email_kind=EmailKind.INVITE, email_state=EmailState.QUEUED,
            email_error=None) or entry

    def pending_email_count(self, limit: int = MAX_SLOT_SIZE) -> int:
        return len(self.repository.pending_emails(limit))

    def dispatch_pending(self, *, limit: int = 200) -> DispatchResult:
        """Drain the queue. Safe to call repeatedly: only queued and failed rows move.

        One founder's failure never stops the batch -- their row is marked `failed`
        with the reason and the next address is tried.
        """
        if self._send is None:
            return DispatchResult()

        sent = failed = skipped = 0
        failures: list[str] = []
        for entry in self.repository.pending_emails(max(1, limit)):
            cohort = (self.repository.get_cohort(entry.cohort_id)
                      if entry.cohort_id else None)
            try:
                ok, error = self._send(entry, entry.email_kind, cohort)
            except Exception as exc:                       # noqa: BLE001 -- see below
                # A sender that raises must not abandon the rest of the queue, and
                # must not leave this row `queued` forever. Record and move on.
                ok, error = False, str(exc)[:500]

            if ok:
                sent += 1
                self.repository.update_entry(
                    entry.entry_id, email_state=EmailState.SENT,
                    email_sent_at=self._now(), email_error=None)
            elif error:
                failed += 1
                failures.append(entry.email)
                self.repository.update_entry(
                    entry.entry_id, email_state=EmailState.FAILED, email_error=error[:500])
            else:
                # Stub mode: no SMTP configured. Not a failure, and not a retry --
                # leaving it queued would make every later drain report the same
                # backlog forever on a deployment that simply does not send mail.
                skipped += 1
                self.repository.update_entry(
                    entry.entry_id, email_state=EmailState.SKIPPED,
                    email_error=None)
        return DispatchResult(sent=sent, failed=failed, skipped=skipped,
                              failures=failures)


def build_beta_service(repository: BetaRepository | None = None, *, sender=None,
                       coupons=None, clock=None, id_factory=None) -> BetaAccessService:
    return BetaAccessService(repository or InMemoryBetaRepository(), sender=sender,
                             coupons=coupons, clock=clock, id_factory=id_factory)
