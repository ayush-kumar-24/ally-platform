"""Pictures on vision territories.

A founder can hang one image on each vision they have written. These tests pin
the parts that are easy to get wrong and invisible when they are: that saving
the sentence never wipes the picture, that a replaced file is cleaned up, that
an image cannot be attached to a vision that does not exist, and that the
in-memory repository behaves like the SQL one rather than merely passing.

No S3 and no bucket configured here, so every upload takes the local-disk
fallback -- which is the path CI and local dev actually run, and the one a
missing credential drops production onto.
"""

import io
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.api.v1.vision.dependencies import (
    get_current_founder_id,
    get_vision_service,
    require_vision,
)
from app.api.v1.vision.router import _local_dir
from app.main import app
from app.vision import InMemoryVisionRepository, build_vision_service

BASE = "/api/v1/vision"
T0 = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)


class StepClock:
    def __init__(self, start=T0, step=timedelta(seconds=1)):
        self._now, self._step = start, step

    def __call__(self):
        v = self._now
        self._now += self._step
        return v


@pytest.fixture
def client():
    repo = InMemoryVisionRepository()
    service = build_vision_service(repo, clock=StepClock())
    app.dependency_overrides[get_current_founder_id] = lambda: 1
    app.dependency_overrides[get_vision_service] = lambda: service
    # Vision is gated on Feature.VISION (Rs 999). These tests are about vision
    # behaviour, not entitlement, and the real gate would pull in get_db and
    # get_founder_record that no vision test provides. The gate is covered in
    # test_plans.py; here it is a no-op so the routes under test are reachable.
    app.dependency_overrides[require_vision] = lambda: None
    http = TestClient(app)
    http.repo = repo
    yield http
    for dep in (get_current_founder_id, get_vision_service, require_vision):
        app.dependency_overrides.pop(dep, None)


@pytest.fixture(autouse=True)
def _clean_uploads():
    """The local fallback writes real files. Sweep this test's own output so a
    run never depends on, or leaves behind, another run's images."""
    before = set(_local_dir().glob("*")) if _local_dir().exists() else set()
    yield
    if _local_dir().exists():
        for f in set(_local_dir().glob("*")) - before:
            f.unlink(missing_ok=True)


def png(colour=(30, 90, 60)):
    buf = io.BytesIO()
    Image.new("RGB", (60, 40), colour).save(buf, format="PNG")
    return buf.getvalue()


def upload(client, key="business", data=None, filename="board.png", content_type="image/png"):
    return client.post(
        f"{BASE}/territories/{key}/image",
        files={"file": (filename, data if data is not None else png(), content_type)},
    )


def write_vision(client, key="business", statement="Runs without me."):
    return client.put(f"{BASE}/territories/{key}", json={"statement": statement, "tag1": "", "tag2": ""})


# --- attaching -------------------------------------------------------------


def test_upload_attaches_an_image_to_a_written_vision(client):
    write_vision(client)
    r = upload(client)
    assert r.status_code == 201
    body = r.json()
    assert body["territory"] == "business"
    assert body["image_url"] and "/uploads/vision/" in body["image_url"]
    assert body["statement"] == "Runs without me."       # text untouched


def test_the_image_shows_up_on_the_next_get(client):
    write_vision(client)
    url = upload(client).json()["image_url"]
    assert client.get(BASE).json()["territories"]["business"]["image_url"] == url


def test_a_territory_with_no_image_reports_null_not_empty_string(client):
    write_vision(client)
    assert client.get(BASE).json()["territories"]["business"]["image_url"] is None


def test_an_unwritten_territory_reports_null(client):
    assert client.get(BASE).json()["territories"]["legacy"]["image_url"] is None


def test_each_territory_holds_its_own_image(client):
    write_vision(client, "business")
    write_vision(client, "legacy", "Something that outlives me.")
    a = upload(client, "business").json()["image_url"]
    b = upload(client, "legacy").json()["image_url"]
    assert a != b
    got = client.get(BASE).json()["territories"]
    assert got["business"]["image_url"] == a
    assert got["legacy"]["image_url"] == b


# --- the failure this whole design is arranged around ----------------------


def test_saving_the_statement_does_not_wipe_the_picture(client):
    """The two are edited independently and arrive on separate requests. A
    naive upsert writes the whole row and silently drops the image."""
    write_vision(client)
    url = upload(client).json()["image_url"]

    r = client.put(f"{BASE}/territories/business",
                   json={"statement": "Runs without me, profitably.", "tag1": "4-day week", "tag2": ""})
    assert r.status_code == 200
    assert r.json()["image_url"] == url                  # in the response...
    assert client.get(BASE).json()["territories"]["business"]["image_url"] == url   # ...and on the next read


def test_the_save_response_reports_the_stored_row_not_the_request(client):
    """Returning the object the caller built would report image_url=None on
    every text save, and the page would blank a picture that is still there."""
    write_vision(client)
    upload(client)
    assert client.put(f"{BASE}/territories/business",
                      json={"statement": "New words.", "tag1": "", "tag2": ""}).json()["image_url"] is not None


# --- replacing and removing ------------------------------------------------


def test_replacing_an_image_gives_a_new_url(client):
    write_vision(client)
    first = upload(client, data=png((30, 90, 60))).json()["image_url"]
    second = upload(client, data=png((200, 30, 30))).json()["image_url"]
    assert first != second
    assert client.get(BASE).json()["territories"]["business"]["image_url"] == second


def test_replacing_an_image_deletes_the_file_it_replaced(client):
    """One image per territory, so the old file has no reader the moment the
    new row is written -- leaving it behind accumulates orphans forever."""
    write_vision(client)
    first = upload(client).json()["image_url"]
    upload(client)
    assert not (_local_dir() / Path(first).name).exists()


def test_delete_removes_the_image_and_keeps_the_statement(client):
    write_vision(client)
    url = upload(client).json()["image_url"]

    r = client.delete(f"{BASE}/territories/business/image")
    assert r.status_code == 200
    assert r.json()["image_url"] is None
    assert r.json()["statement"] == "Runs without me."
    assert not (_local_dir() / Path(url).name).exists()


def test_delete_on_an_unwritten_territory_is_a_404(client):
    assert client.delete(f"{BASE}/territories/legacy/image").status_code == 404


# --- refusals --------------------------------------------------------------


def test_cannot_hang_an_image_on_a_vision_that_does_not_exist(client):
    """A card with a picture and no sentence is not a thing this page has a
    place for."""
    assert upload(client, "legacy").status_code == 404


def test_a_refused_attach_leaves_no_orphan_file(client):
    before = set(_local_dir().glob("*")) if _local_dir().exists() else set()
    upload(client, "legacy")
    after = set(_local_dir().glob("*")) if _local_dir().exists() else set()
    assert after == before


def test_unknown_territory_key_is_rejected(client):
    assert upload(client, "not_a_territory").status_code in (404, 422)


def test_a_pdf_is_refused(client):
    write_vision(client)
    r = upload(client, data=b"%PDF-1.4", filename="deck.pdf", content_type="application/pdf")
    assert r.status_code == 422
    # The global handler reports AppError as {error, message, request_id} --
    # there is no "detail" key here, that is FastAPI's own HTTPException shape.
    assert "PNG" in r.json()["message"]


def test_an_empty_file_is_refused(client):
    write_vision(client)
    assert upload(client, data=b"").status_code == 422


def test_an_oversized_image_is_refused(client):
    write_vision(client)
    assert upload(client, data=b"\x89PNG\r\n\x1a\n" + b"0" * (5 * 1024 * 1024 + 1)).status_code == 422


def test_a_refused_upload_leaves_the_previous_image_alone(client):
    write_vision(client)
    good = upload(client).json()["image_url"]
    upload(client, data=b"%PDF-1.4", filename="x.pdf", content_type="application/pdf")
    assert client.get(BASE).json()["territories"]["business"]["image_url"] == good
    assert (_local_dir() / Path(good).name).exists()


# --- filenames -------------------------------------------------------------


def test_the_filename_carries_an_unguessable_component(client):
    """The serving route is public and reads no database, so the randomness in
    this name IS the access control on the picture."""
    write_vision(client)
    name = Path(upload(client).json()["image_url"]).name
    founder, territory, random, ext = name.split(".")
    assert (founder, territory, ext) == ("1", "business", "png")
    assert len(random) == 32
