"""SqlAttachmentRepository -- live DB conformance + the actual resume proof.

Business-logic behaviour (duplicate detection, lifecycle rules) is already covered
against the in-memory repository in test_ai_chat_attachments.py and is repository-
independent. This file exercises what IS repository-specific: durable persistence,
the string<->integer id mapping, derived (not stored) extension/attachment_type,
and -- the actual point of this fix -- that an attachment uploaded in one DB
session is found from a completely separate session.

Uses a throwaway founder + a real conversation row (file_uploads.conversation_id
is a real FK), cleaned up in reverse-FK order with an explicit zero-residue check.
"""

from datetime import datetime, timedelta, timezone
from itertools import count
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.ai_chat.attachments.schemas import AttachmentStatus, AttachmentType, SupportedMimeType
from app.ai_chat.attachments.service import build_attachment_service
from app.ai_chat.attachments.sql_repository import SqlAttachmentRepository
from app.ai_chat.repositories.sql_conversation import SqlConversationRepository
from app.ai_chat.services.conversation import build_conversation_service
from app.db.session import SessionLocal

T0 = datetime(2026, 7, 28, 13, 0, 0, tzinfo=timezone.utc)


class FakeClock:
    def __init__(self, start=T0, step=timedelta(seconds=1)):
        self._now, self._step = start, step

    def now(self):
        v = self._now
        self._now += self._step
        return v


def _ids(prefix="att"):
    c = count(1)
    return lambda: f"{prefix}-{uuid4().hex[:8]}-{next(c)}"


@pytest.fixture
def founder_and_conversation():
    """A throwaway founder + one conversation (for the file_uploads FK), cleaned
    up in reverse-FK order: file_uploads -> conversations -> founders -> auth.users."""
    db = SessionLocal()
    uid = uuid4()
    email = f"attrepo+{uid.hex[:8]}@verify.test"
    db.execute(text(
        "insert into auth.users (id,instance_id,aud,role,email) values "
        "(:i,'00000000-0000-0000-0000-000000000000','authenticated','authenticated',:e)"
    ), {"i": str(uid), "e": email})
    db.commit()
    fid = db.execute(text(
        "insert into founders (user_id,full_name,email) values (:u,:n,:e) returning founder_id"
    ), {"u": str(uid), "n": "Attach Repo Test", "e": email}).scalar()
    db.commit()
    conv = build_conversation_service(
        SqlConversationRepository(db), clock=FakeClock(), id_factory=_ids("conv")
    ).create_conversation(fid)
    db.commit()
    db.close()
    yield fid, conv.conversation_id
    cleanup = SessionLocal()
    cleanup.execute(text("delete from file_uploads where founder_id=:f"), {"f": fid})
    cleanup.execute(text("delete from conversations where founder_id=:f"), {"f": fid})
    cleanup.execute(text("delete from founders where founder_id=:f"), {"f": fid})
    cleanup.execute(text("delete from auth.users where id=:u"), {"u": str(uid)})
    cleanup.commit()
    residue = {
        t: cleanup.execute(text(f"select count(*) from {t} where founder_id=:f"), {"f": fid}).scalar()
        for t in ("file_uploads", "conversations")
    }
    cleanup.close()
    assert all(v == 0 for v in residue.values()), f"residue left behind: {residue}"


def svc(db):
    return build_attachment_service(SqlAttachmentRepository(db), clock=FakeClock(), id_factory=_ids())


CONTENT = b"%PDF-1.4 fake pdf bytes for a checksum"


# --- create / read round-trip -------------------------------------------------

def test_add_persists_and_reads_back(founder_and_conversation):
    fid, conv_id = founder_and_conversation
    db = SessionLocal()
    a = svc(db).add_attachment(conv_id, fid, "report.pdf", CONTENT)
    db.commit()
    fetched = svc(db).get_attachment(a.attachment_id)
    assert fetched.metadata.filename == "report.pdf"
    assert fetched.metadata.mime_type == SupportedMimeType.PDF
    assert fetched.status is AttachmentStatus.ACTIVE
    db.close()


def test_extension_and_type_are_derived_not_stored(founder_and_conversation):
    """extension/attachment_type have no DB column -- prove they still round-trip
    correctly, recomputed from file_name/file_type on read."""
    fid, conv_id = founder_and_conversation
    db = SessionLocal()
    a = svc(db).add_attachment(conv_id, fid, "photo.PNG", CONTENT)
    db.commit()
    fetched = svc(db).get_attachment(a.attachment_id)
    assert fetched.metadata.extension == "png"           # lower-cased, derived
    assert fetched.metadata.attachment_type == AttachmentType.IMAGE
    db.close()


def test_checksum_persists_for_duplicate_detection(founder_and_conversation):
    fid, conv_id = founder_and_conversation
    db = SessionLocal()
    s = svc(db)
    s.add_attachment(conv_id, fid, "a.txt", b"same bytes")
    db.commit()
    from app.ai_chat.attachments.errors import DuplicateAttachmentError
    with pytest.raises(DuplicateAttachmentError):
        s.add_attachment(conv_id, fid, "b.txt", b"same bytes")  # same checksum
    db.close()


def test_tags_and_extra_round_trip(founder_and_conversation):
    fid, conv_id = founder_and_conversation
    db = SessionLocal()
    a = svc(db).add_attachment(
        conv_id, fid, "notes.txt", CONTENT, tags=("important", "financials"),
        extra={"source": "onboarding"},
    )
    db.commit()
    fetched = svc(db).get_attachment(a.attachment_id)
    assert fetched.tags == ("important", "financials")
    assert fetched.extra == {"source": "onboarding"}
    db.close()


# --- THE ACTUAL FIX: resume across a completely separate DB session ---------

def test_attachment_found_across_separate_sessions(founder_and_conversation):
    """The one the in-memory repository could never pass: an attachment uploaded
    in one DB session (simulating one server process) is fully readable from a
    totally independent session (simulating another)."""
    fid, conv_id = founder_and_conversation
    db1 = SessionLocal()
    a = svc(db1).add_attachment(conv_id, fid, "cross-process.pdf", CONTENT)
    db1.commit()
    db1.close()   # the "process" that uploaded it is gone

    db2 = SessionLocal()
    s2 = svc(db2)
    fetched = s2.get_attachment(a.attachment_id)
    assert fetched.metadata.filename == "cross-process.pdf"
    listed = s2.list_attachments(conv_id)
    assert len(listed) == 1 and listed[0].attachment_id == a.attachment_id

    # continue the lifecycle from the new session
    archived = s2.archive_attachment(a.attachment_id)
    db2.commit()
    assert archived.status is AttachmentStatus.ARCHIVED
    db2.close()


# --- lifecycle + purge --------------------------------------------------------

def test_archive_restore_delete_persist(founder_and_conversation):
    fid, conv_id = founder_and_conversation
    db = SessionLocal()
    s = svc(db)
    a = s.add_attachment(conv_id, fid, "x.txt", CONTENT)
    s.archive_attachment(a.attachment_id)
    db.commit()
    assert s.get_attachment(a.attachment_id).status is AttachmentStatus.ARCHIVED

    s.restore_attachment(a.attachment_id)
    db.commit()
    assert s.get_attachment(a.attachment_id).status is AttachmentStatus.ACTIVE

    s.delete_attachment(a.attachment_id)
    db.commit()
    assert s.get_attachment(a.attachment_id).status is AttachmentStatus.DELETED
    db.close()


def test_list_excludes_deleted_by_default(founder_and_conversation):
    fid, conv_id = founder_and_conversation
    db = SessionLocal()
    s = svc(db)
    keep = s.add_attachment(conv_id, fid, "keep.txt", b"keep bytes")
    gone = s.add_attachment(conv_id, fid, "gone.txt", b"gone bytes")
    s.delete_attachment(gone.attachment_id)
    db.commit()
    visible = {a.attachment_id for a in s.list_attachments(conv_id)}
    assert visible == {keep.attachment_id}
    db.close()


def test_purge_hard_removes_row(founder_and_conversation):
    fid, conv_id = founder_and_conversation
    db = SessionLocal()
    s = svc(db)
    a = s.add_attachment(conv_id, fid, "purge-me.txt", CONTENT)
    db.commit()
    repo = SqlAttachmentRepository(db)
    assert repo.purge(a.attachment_id) is True
    db.commit()
    remaining = db.execute(text(
        "select count(*) from file_uploads where external_id=:a"
    ), {"a": a.attachment_id}).scalar()
    assert remaining == 0
    db.close()
