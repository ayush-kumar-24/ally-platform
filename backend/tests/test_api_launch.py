"""The launch gate over HTTP.

The point of these (over the service tests) is what only the transport can get
wrong: the public status endpoint really is reachable without a token, the
launch button really is Super Admin only on the server rather than merely
hidden in the panel, and a refused press really is a 409 the UI can act on.
"""

from datetime import datetime, timedelta, timezone
from itertools import count
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.admin.panel_audit import AuditRecorder, InMemoryPanelAuditRepository
from app.admin.rbac import PanelRole
from app.api.v1.admin.panel_dependencies import (
    PanelAdmin,
    get_panel_admin,
    get_panel_service,
)
from app.core.container import container
from app.db.session import get_db
from app.launch import InMemoryLaunchRepository, LaunchService
from app.main import app

PUBLIC = "/api/v1/launch/status"
ADMIN = "/api/v1/admin/launch"
T0 = datetime(2026, 9, 9, 18, 0, tzinfo=timezone.utc)


class Clock:
    def __init__(self) -> None:
        self.now = T0

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


@pytest.fixture
def client(monkeypatch):
    clock = Clock()
    launch = LaunchService(InMemoryLaunchRepository(), clock=clock)
    # One service instance for both the public and the admin routes, so a test
    # can press a button as an admin and then read the result as a stranger --
    # which is exactly the sequence launch day consists of.
    monkeypatch.setattr(container, "launch_service", lambda db: launch)

    audit_repo = InMemoryPanelAuditRepository()
    c = count(1)
    panel = SimpleNamespace(audit=AuditRecorder(
        audit_repo, clock=lambda: T0, id_factory=lambda: f"e-{next(c)}"))

    current = {"role": PanelRole.SUPER_ADMIN}
    app.dependency_overrides[get_db] = lambda: None
    app.dependency_overrides[get_panel_admin] = lambda: PanelAdmin(
        admin_id=99, email="viraj@goxl.in", role=current["role"])
    app.dependency_overrides[get_panel_service] = lambda: panel
    yield SimpleNamespace(http=TestClient(app), current=current, clock=clock,
                          audit=audit_repo)
    for dep in (get_db, get_panel_admin, get_panel_service):
        app.dependency_overrides.pop(dep, None)


def as_role(client, role):
    client.current["role"] = role


def run_countdown(client, seconds=10):
    """Arm, start, and let the clock run out -- the state every launch test
    actually starts from."""
    client.http.post(f"{ADMIN}/arm", json={"countdown_seconds": seconds})
    client.http.post(f"{ADMIN}/countdown", json={})
    client.clock.advance(seconds)


# --- the public endpoint ----------------------------------------------------


def test_status_is_readable_without_a_token():
    """Unauthenticated by design: the people who most need this answer are the
    ones who cannot sign in yet."""
    body = TestClient(app).get(PUBLIC).json()
    assert set(body) >= {"is_open", "state", "seconds_remaining"}


def test_status_is_never_cached():
    """A CDN holding this for even a few seconds is a room whose countdowns
    disagree, and a founder still on the holding screen after the doors open."""
    assert TestClient(app).get(PUBLIC).headers["cache-control"] == "no-store"


def test_public_status_tracks_the_gate(client):
    assert client.http.get(PUBLIC).json()["is_open"] is True

    client.http.post(f"{ADMIN}/arm", json={"countdown_seconds": 10})
    closed = client.http.get(PUBLIC).json()
    assert closed["is_open"] is False and closed["state"] == "armed"

    client.http.post(f"{ADMIN}/countdown", json={})
    client.clock.advance(4)
    counting = client.http.get(PUBLIC).json()
    assert counting["state"] == "counting"
    assert counting["seconds_remaining"] == pytest.approx(6.0)

    client.http.post(f"{ADMIN}/launch")
    # Still counting from the server's point of view -- 4s in on a 10s clock.
    assert client.http.get(PUBLIC).json()["is_open"] is False

    client.clock.advance(6)
    client.http.post(f"{ADMIN}/launch")
    opened = client.http.get(PUBLIC).json()
    assert opened["is_open"] is True and opened["state"] == "launched"


# --- authorization ----------------------------------------------------------


@pytest.mark.parametrize("path", ["/arm", "/countdown", "/abort", "/launch"])
@pytest.mark.parametrize("role", [PanelRole.ADMIN, PanelRole.SUPPORT])
def test_only_super_admin_may_press_anything(client, path, role):
    """Launching is the most public, least reversible action in the panel.
    Enforced on the server -- hiding the button is a usability nicety."""
    as_role(client, role)
    assert client.http.post(f"{ADMIN}{path}", json={}).status_code == 403
    assert client.http.get(PUBLIC).json()["is_open"] is True


@pytest.mark.parametrize("role", [PanelRole.ADMIN, PanelRole.SUPPORT])
def test_the_rest_of_the_team_may_watch(client, role):
    """Following along on the day needs no power to press."""
    as_role(client, role)
    assert client.http.get(ADMIN).status_code == 200


# --- the buttons ------------------------------------------------------------


def test_can_launch_flips_only_when_the_countdown_reaches_zero(client):
    """The panel renders its button from this field rather than its own timer,
    so the rule the server enforces is the rule the UI shows."""
    client.http.post(f"{ADMIN}/arm", json={"countdown_seconds": 10})
    assert client.http.post(f"{ADMIN}/countdown", json={}).json()["can_launch"] is False

    client.clock.advance(9)
    assert client.http.get(ADMIN).json()["can_launch"] is False

    client.clock.advance(1)
    assert client.http.get(ADMIN).json()["can_launch"] is True


def test_launching_early_is_a_409_not_a_silent_no_op(client):
    client.http.post(f"{ADMIN}/arm", json={"countdown_seconds": 10})
    client.http.post(f"{ADMIN}/countdown", json={})
    client.clock.advance(5)

    assert client.http.post(f"{ADMIN}/launch").status_code == 409
    assert client.http.get(PUBLIC).json()["is_open"] is False


def test_abort_before_zero_keeps_the_doors_shut(client):
    client.http.post(f"{ADMIN}/arm", json={"countdown_seconds": 10})
    client.http.post(f"{ADMIN}/countdown", json={})
    client.clock.advance(6)

    aborted = client.http.post(f"{ADMIN}/abort").json()
    assert aborted["state"] == "armed" and aborted["can_launch"] is False
    client.clock.advance(60)
    assert client.http.get(PUBLIC).json()["is_open"] is False


def test_launch_is_recorded_against_the_person_who_pressed_it(client):
    run_countdown(client)
    launched = client.http.post(f"{ADMIN}/launch").json()
    assert launched["state"] == "launched" and launched["launched_by"] == 99

    rows, _ = client.audit.list(limit=20)
    events = {e.action for e in rows}
    assert {"launch.arm", "launch.countdown", "launch.launch"} <= events


def test_relaunching_is_refused_or_a_no_op_but_never_a_second_launch(client):
    run_countdown(client)
    first = client.http.post(f"{ADMIN}/launch").json()
    client.clock.advance(3600)

    again = client.http.post(f"{ADMIN}/launch")
    assert again.status_code == 200
    assert again.json()["launched_at"] == first["launched_at"]

    # And nothing puts a live platform back behind the countdown.
    for path in ("/arm", "/countdown", "/abort"):
        assert client.http.post(f"{ADMIN}{path}", json={}).status_code == 409
    assert client.http.get(PUBLIC).json()["is_open"] is True


@pytest.mark.parametrize("seconds", [0, 2, 301])
def test_countdown_length_is_validated_at_the_edge(client, seconds):
    assert client.http.post(f"{ADMIN}/arm",
                            json={"countdown_seconds": seconds}).status_code == 422
