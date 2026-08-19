"""A founder gets their real report PDF, or an honest "not yet". Never a stand-in.

Report exports used to render on every download and fall back to a plain
reportlab document whenever Gotenberg was unreachable. Both paths return 200
with a real application/pdf body, so a founder who downloaded during a blip
received the wrong document -- and nothing ever tried again. The whole point of
what replaced it is that a missing PDF is recoverable and a wrong one is not.

The properties below are the ones that make that true. They are tested against
fakes rather than a live Gotenberg and a live bucket, because what matters here
is the decision logic -- which path runs, what is written, and what the founder
is told -- not that httpx and boto3 work.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.api.v1.reports import pdf_delivery


class _Db:
    """Enough Session for these functions: they only ever commit or roll back."""

    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class _Store:
    def __init__(self, *, blob: bytes | None = None, fail_put: bool = False):
        self.blob = blob
        self.fail_put = fail_put
        self.puts: list[tuple[str, bytes]] = []

    def get(self, key):
        return self.blob

    def put(self, key, content, *, content_type):
        if self.fail_put:
            raise RuntimeError("bucket unavailable")
        self.puts.append((key, content))


def _report(**over):
    base = dict(report_id=74, pdf_storage_key=None, pdf_requested_at=None)
    base.update(over)
    return SimpleNamespace(**base)


@pytest.fixture
def no_storage(monkeypatch):
    monkeypatch.setattr(pdf_delivery, "_storage", lambda: None)


@pytest.fixture
def renders_ok(monkeypatch):
    monkeypatch.setattr(pdf_delivery, "build_report_html", lambda n: "<html></html>")
    monkeypatch.setattr(pdf_delivery, "render_pdf", lambda html, *, base_url: b"%PDF-real")


@pytest.fixture
def renderer_down(monkeypatch):
    monkeypatch.setattr(pdf_delivery, "build_report_html", lambda n: "<html></html>")

    def _boom(html, *, base_url):
        raise pdf_delivery.GotenbergError("connection refused")

    monkeypatch.setattr(pdf_delivery, "render_pdf", _boom)


# --- the renderer is down ---------------------------------------------------

def test_no_substitute_document_is_ever_produced(renderer_down, no_storage):
    """The single property this module exists for."""
    assert pdf_delivery.render_and_store(_Db(), _report(), object()) is None


def test_a_failed_render_writes_nothing(renderer_down, no_storage):
    """The request has to stay retryable: a founder who tries again in a minute,
    once the renderer is back, must get a PDF and not a half-written row."""
    db, report = _Db(), _report()

    pdf_delivery.render_and_store(db, report, object())

    assert db.commits == 0
    assert report.pdf_storage_key is None


def test_the_wait_is_recorded_once(monkeypatch):
    """The sweep should serve whoever has been waiting longest, so the FIRST
    attempt's timestamp is the one that counts -- a founder clicking repeatedly
    must not keep pushing themselves to the back of the queue."""
    db = _Db()
    first = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)
    report = _report(pdf_requested_at=first)

    pdf_delivery.mark_pdf_requested(db, report)

    assert report.pdf_requested_at == first
    assert db.commits == 0


# --- the renderer is up -----------------------------------------------------

def test_a_rendered_pdf_is_stored_and_pointed_at(renders_ok, monkeypatch):
    store = _Store()
    monkeypatch.setattr(pdf_delivery, "_storage", lambda: store)
    db, report = _Db(), _report(pdf_requested_at=datetime.now(timezone.utc))

    pdf = pdf_delivery.render_and_store(db, report, object())

    assert pdf == b"%PDF-real"
    assert store.puts == [(pdf_delivery.storage_key(74), b"%PDF-real")]
    assert report.pdf_storage_key == pdf_delivery.storage_key(74)


def test_the_wait_clears_even_when_nothing_can_be_stored(renders_ok, no_storage):
    """Found live. `pdf_requested_at` was cleared only alongside a successful
    PUT, so wherever storage is not configured the row stayed pending forever
    and the sweep re-rendered the same report on every pass.

    The flag means "a founder could not download", and that stops being true the
    moment rendering works again -- whether or not a copy was kept.
    """
    db, report = _Db(), _report(pdf_requested_at=datetime.now(timezone.utc))

    assert pdf_delivery.render_and_store(db, report, object()) == b"%PDF-real"
    assert report.pdf_requested_at is None


def test_a_storage_failure_still_serves_the_founder(renders_ok, monkeypatch):
    """The PDF is correct; only the copy failed. Refusing to serve it would
    punish the founder for an infrastructure problem they cannot see."""
    monkeypatch.setattr(pdf_delivery, "_storage", lambda: _Store(fail_put=True))
    db, report = _Db(), _report()

    assert pdf_delivery.render_and_store(db, report, object()) == b"%PDF-real"
    assert report.pdf_storage_key is None


# --- serving a kept copy ----------------------------------------------------

def test_a_stored_pdf_is_served_without_rendering(monkeypatch):
    monkeypatch.setattr(pdf_delivery, "_storage", lambda: _Store(blob=b"%PDF-kept"))
    assert pdf_delivery.stored_pdf(_report(pdf_storage_key="reports/74/x.pdf")) == b"%PDF-kept"


def test_an_unreadable_stored_pdf_falls_through_to_a_fresh_render(monkeypatch):
    """A key that points at nothing (bucket wiped, object expired) must not be a
    dead end -- returning None sends the caller down the render path, which also
    repairs the stored copy."""
    class _Broken:
        def get(self, key):
            raise RuntimeError("no such key")

    monkeypatch.setattr(pdf_delivery, "_storage", lambda: _Broken())
    assert pdf_delivery.stored_pdf(_report(pdf_storage_key="reports/74/x.pdf")) is None


def test_no_key_means_no_storage_lookup(monkeypatch):
    called = []
    monkeypatch.setattr(pdf_delivery, "_storage", lambda: called.append(1))
    assert pdf_delivery.stored_pdf(_report()) is None
    assert called == []
