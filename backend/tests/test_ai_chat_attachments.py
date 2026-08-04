"""Tests for File Attachments (Phase 6, Milestone 4). Metadata only -- no parsing."""

from datetime import datetime, timedelta, timezone
from itertools import count

import pytest

from app.ai_chat.attachments import (
    AttachmentConfig,
    AttachmentNotFoundError,
    AttachmentStatus,
    AttachmentTooLargeError,
    AttachmentType,
    DuplicateAttachmentError,
    InvalidAttachmentError,
    SupportedMimeType,
    UnsupportedAttachmentError,
    build_attachment_service,
    checksum,
)
from concurrent.futures import ThreadPoolExecutor

T0 = datetime(2026, 7, 28, 13, 0, 0, tzinfo=timezone.utc)


class FakeClock:
    def __init__(self, start=T0, step=timedelta(seconds=1)):
        self._now, self._step = start, step

    def now(self):
        v = self._now
        self._now += self._step
        return v


def _ids():
    c = count(1)
    return lambda: f"att-{next(c)}"


def svc(**cfg):
    config = AttachmentConfig(**cfg) if cfg else None
    return build_attachment_service(clock=FakeClock(), id_factory=_ids(), config=config)


def add(service, *, conv="c1", founder=1, filename="report.pdf", content=b"%PDF-1.4 data"):
    return service.add_attachment(conv, founder, filename, content)


# --- validation -------------------------------------------------------------


def test_unsupported_extension_rejected():
    with pytest.raises(UnsupportedAttachmentError):
        add(svc(), filename="archive.zip", content=b"PK\x03\x04")


def test_missing_extension_rejected():
    with pytest.raises(UnsupportedAttachmentError):
        add(svc(), filename="noext", content=b"data")


def test_empty_content_rejected():
    with pytest.raises(InvalidAttachmentError):
        add(svc(), content=b"")


def test_oversize_rejected():
    with pytest.raises(AttachmentTooLargeError):
        svc(max_size_bytes=4).add_attachment("c1", 1, "a.txt", b"way too big")


# --- mime + type detection --------------------------------------------------


MIME_CASES = [
    ("a.pdf", SupportedMimeType.PDF, AttachmentType.DOCUMENT),
    ("a.docx", SupportedMimeType.DOCX, AttachmentType.DOCUMENT),
    ("a.txt", SupportedMimeType.TXT, AttachmentType.TEXT),
    ("a.md", SupportedMimeType.MARKDOWN, AttachmentType.TEXT),
    ("a.markdown", SupportedMimeType.MARKDOWN, AttachmentType.TEXT),
    ("a.png", SupportedMimeType.PNG, AttachmentType.IMAGE),
    ("a.jpg", SupportedMimeType.JPEG, AttachmentType.IMAGE),
    ("a.jpeg", SupportedMimeType.JPEG, AttachmentType.IMAGE),
    ("a.gif", SupportedMimeType.GIF, AttachmentType.IMAGE),
    ("a.webp", SupportedMimeType.WEBP, AttachmentType.IMAGE),
    ("a.csv", SupportedMimeType.CSV, AttachmentType.SPREADSHEET),
]


@pytest.mark.parametrize("filename,mime,atype", MIME_CASES)
def test_mime_and_type_detection(filename, mime, atype):
    a = add(svc(), filename=filename, content=b"bytes")
    assert a.metadata.mime_type == mime and a.metadata.attachment_type == atype


def test_uppercase_extension_detected():
    a = add(svc(), filename="PHOTO.JPG", content=b"img")
    assert a.metadata.mime_type == SupportedMimeType.JPEG and a.metadata.extension == "jpg"


# --- checksum + size --------------------------------------------------------


def test_checksum_and_size():
    a = add(svc(), content=b"hello")
    assert a.metadata.checksum == checksum(b"hello") and a.metadata.size_bytes == 5


def test_checksum_differs_for_different_content():
    s = svc()
    a = s.add_attachment("c1", 1, "a.txt", b"one")
    b = s.add_attachment("c1", 1, "b.txt", b"two")
    assert a.metadata.checksum != b.metadata.checksum


# --- duplicate detection ----------------------------------------------------


def test_duplicate_same_content_rejected():
    s = svc()
    add(s, content=b"same")
    with pytest.raises(DuplicateAttachmentError):
        add(s, filename="copy.pdf", content=b"same")


def test_duplicates_allowed_when_configured():
    s = svc(allow_duplicates=True)
    add(s, content=b"same")
    add(s, filename="copy.pdf", content=b"same")           # no raise
    assert len(s.list_attachments("c1")) == 2


def test_same_content_different_conversation_is_not_duplicate():
    s = svc()
    s.add_attachment("c1", 1, "a.pdf", b"same")
    s.add_attachment("c2", 1, "a.pdf", b"same")            # different conversation -> fine
    assert len(s.list_attachments("c1")) == 1 and len(s.list_attachments("c2")) == 1


# --- multiple attachments + listing -----------------------------------------


def test_multiple_attachments_per_conversation():
    s = svc()
    s.add_attachment("c1", 1, "a.pdf", b"a")
    s.add_attachment("c1", 1, "b.png", b"b")
    s.add_attachment("c1", 1, "c.csv", b"c")
    assert len(s.list_attachments("c1")) == 3


# --- lifecycle --------------------------------------------------------------


def test_archive_hidden_by_default():
    s = svc()
    a = add(s)
    s.archive_attachment(a.attachment_id)
    assert s.list_attachments("c1") == ()
    assert len(s.list_attachments("c1", include_archived=True)) == 1
    assert s.get_attachment(a.attachment_id).status == AttachmentStatus.ARCHIVED


def test_delete_soft_and_restore():
    s = svc()
    a = add(s)
    s.delete_attachment(a.attachment_id)
    assert s.get_attachment(a.attachment_id).is_deleted
    assert s.list_attachments("c1") == ()
    restored = s.restore_attachment(a.attachment_id)
    assert restored.is_active and restored.deleted_at is None


def test_archive_sets_timestamp_then_restore_clears():
    s = svc()
    a = add(s)
    archived = s.archive_attachment(a.attachment_id)
    assert archived.archived_at is not None
    assert s.restore_attachment(a.attachment_id).archived_at is None


# --- content storage/read (chat-grounding read path) -------------------------


def test_content_round_trips():
    s = svc()
    a = add(s, content=b"%PDF-1.4 the actual bytes")
    assert s.get_content(a.attachment_id) == b"%PDF-1.4 the actual bytes"


def test_content_missing_for_unknown_attachment():
    assert svc().get_content("nope") is None


def test_get_missing_raises():
    with pytest.raises(AttachmentNotFoundError):
        svc().get_attachment("nope")


def test_lifecycle_missing_raises():
    s = svc()
    for op in (s.archive_attachment, s.restore_attachment, s.delete_attachment):
        with pytest.raises(AttachmentNotFoundError):
            op("nope")


# --- summary ----------------------------------------------------------------


def test_summary_counts_and_bytes():
    s = svc()
    s.add_attachment("c1", 1, "a.pdf", b"1234")            # 4 bytes, active
    b = s.add_attachment("c1", 1, "b.png", b"56")          # 2 bytes
    s.archive_attachment(b.attachment_id)
    summary = s.summarize("c1")
    assert summary.total == 2 and summary.active == 1 and summary.archived == 1
    assert summary.total_bytes == 4                        # only active bytes counted
    assert summary.counts_by_type["document"] == 1 and summary.counts_by_type["image"] == 1


# --- determinism + concurrency ----------------------------------------------


def test_deterministic_execution():
    a = add(svc())
    b = add(svc())
    assert a == b                                          # same id, timestamps, checksum, metadata


def test_concurrent_attachment_operations():
    s = build_attachment_service()                        # uuid ids, thread-safe repo

    def upload(i):
        return s.add_attachment("shared", 1, f"file{i}.txt", f"content-{i}".encode()).attachment_id

    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(upload, range(30)))
    assert len(set(ids)) == 30 and len(s.list_attachments("shared")) == 30
