"""AccountDeletionExecutor -- live DB regression tests.

Covers the DPDP/GDPR erasure-sweep bug found in the pre-beta audit:
_HARD_DELETE_TABLES deleted `conversations` before `file_uploads` (whose
conversation_id FK has no ondelete) and never touched `admin_notes` at all
(whose linked_call_id FK to discovery_calls has no ondelete either) -- both
raised a swallowed IntegrityError, and the sweep still stamped
deletion_executed_at as if erasure had completed while those rows survived.

Uses a throwaway founder (real auth.users + founders rows), deleted in
reverse-FK order, with an explicit zero-residue check -- same pattern as
test_sql_conversation_repository.py.
"""

from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.session import SessionLocal
from app.privacy import deletion_executor as deletion_executor_module
from app.privacy.deletion_executor import AccountDeletionExecutor, _HARD_DELETE_TABLES


@pytest.fixture
def seeded_founder():
    """A throwaway founder with a conversation + file upload + discovery call
    + admin note attached -- the exact shape that previously triggered the
    swallowed FK-violation bug. Cleaned up afterwards regardless of whether
    the test's own deletion sweep already removed the rows."""
    db = SessionLocal()
    uid = uuid4()
    email = f"delexec+{uid.hex[:8]}@verify.test"
    db.execute(text(
        "insert into auth.users (id,instance_id,aud,role,email) values "
        "(:i,'00000000-0000-0000-0000-000000000000','authenticated','authenticated',:e)"
    ), {"i": str(uid), "e": email})
    db.commit()
    fid = db.execute(text(
        "insert into founders (user_id,full_name,email) values (:u,:n,:e) returning founder_id"
    ), {"u": str(uid), "n": "Deletion Exec Test", "e": email}).scalar()

    cid = db.execute(text(
        "insert into conversations (founder_id, title, conversation_type, external_id) "
        "values (:f, 'test', 'chat', :x) returning conversation_id"
    ), {"f": fid, "x": f"delexec-{uid.hex[:8]}"}).scalar()

    db.execute(text(
        "insert into file_uploads (founder_id, conversation_id, file_name, "
        "file_type, file_size_bytes, upload_category, external_id, checksum) "
        "values (:f, :c, 'x.pdf', 'application/pdf', 10, 'file', :x, :ck)"
    ), {"f": fid, "c": cid, "x": f"delexec-upload-{uid.hex[:8]}", "ck": uid.hex})

    call_id = db.execute(text(
        "insert into discovery_calls (founder_id, status, scheduled_at) "
        "values (:f, 'pending', now()) returning call_id"
    ), {"f": fid}).scalar()

    db.execute(text(
        "insert into admin_notes (founder_id, created_by, note_type, note_content, "
        "linked_call_id) values (:f, 'test-admin', 'general', 'note body', :c)"
    ), {"f": fid, "c": call_id})

    db.commit()
    db.close()
    yield fid, uid

    cleanup = SessionLocal()
    cleanup.execute(text("delete from admin_notes where founder_id=:f"), {"f": fid})
    cleanup.execute(text("delete from file_uploads where founder_id=:f"), {"f": fid})
    cleanup.execute(text("delete from discovery_calls where founder_id=:f"), {"f": fid})
    cleanup.execute(text("delete from conversations where founder_id=:f"), {"f": fid})
    cleanup.execute(text("delete from founders where founder_id=:f"), {"f": fid})
    cleanup.execute(text("delete from auth.users where id=:u"), {"u": str(uid)})
    cleanup.commit()
    residue = {
        t: cleanup.execute(text(f"select count(*) from {t} where founder_id=:f"), {"f": fid}).scalar()
        for t in ("admin_notes", "file_uploads", "discovery_calls", "conversations")
    }
    cleanup.close()
    assert all(v == 0 for v in residue.values()), f"residue left behind: {residue}"


def test_sweep_deletes_conversation_and_admin_note_without_error(seeded_founder):
    """Regression test for the exact bug: a founder with an uploaded file and
    an admin note linked to a discovery call must have BOTH fully removed,
    not silently skipped behind a swallowed IntegrityError."""
    fid, _ = seeded_founder
    db = SessionLocal()
    try:
        result = AccountDeletionExecutor(db).run(fid)

        assert result.hard_deleted.get("conversations", 0) == 1
        assert result.hard_deleted.get("file_uploads", 0) == 1
        assert result.hard_deleted.get("admin_notes", 0) == 1
        assert result.hard_deleted.get("discovery_calls", 0) == 1
        assert result.executed_at is not None

        remaining = {
            t: db.execute(text(f"select count(*) from {t} where founder_id=:f"), {"f": fid}).scalar()
            for t in ("conversations", "file_uploads", "admin_notes", "discovery_calls")
        }
        assert all(v == 0 for v in remaining.values()), remaining

        row = db.execute(
            text("select deletion_executed_at, email from founders where founder_id=:f"),
            {"f": fid},
        ).one()
        assert row.deletion_executed_at is not None
        assert row.email != f"delexec+{'x'}@verify.test"  # anonymized, not the real address
    finally:
        db.close()


def test_hard_delete_table_order_is_dependency_safe():
    """Structural guard: file_uploads before conversations, admin_notes
    before discovery_calls. Whoever edits this list next trips this
    assertion instead of silently reintroducing the ordering bug."""
    order = {t: i for i, t in enumerate(_HARD_DELETE_TABLES)}
    assert order["file_uploads"] < order["conversations"]
    assert order["admin_notes"] < order["discovery_calls"]


def test_integrity_error_aborts_without_stamping_completion(seeded_founder, monkeypatch):
    """Reproduce the ORIGINAL bug's ordering on purpose (conversations before
    file_uploads) to prove the fix: the sweep must now raise rather than
    swallow the FK violation, and deletion_executed_at must stay NULL so
    find_due_for_deletion() retries this founder instead of the system
    believing erasure already happened."""
    fid, _ = seeded_founder
    bad_order = tuple(
        t for t in _HARD_DELETE_TABLES if t not in ("conversations", "file_uploads")
    ) + ("conversations", "file_uploads")
    monkeypatch.setattr(deletion_executor_module, "_HARD_DELETE_TABLES", bad_order)

    db = SessionLocal()
    try:
        with pytest.raises(Exception):
            AccountDeletionExecutor(db).run(fid)
        db.rollback()

        row = db.execute(
            text("select deletion_executed_at from founders where founder_id=:f"),
            {"f": fid},
        ).one()
        assert row.deletion_executed_at is None

        still_there = db.execute(
            text("select count(*) from conversations where founder_id=:f"), {"f": fid}
        ).scalar()
        assert still_there == 1, "conversation row must survive an aborted, non-committed sweep"
    finally:
        db.close()
