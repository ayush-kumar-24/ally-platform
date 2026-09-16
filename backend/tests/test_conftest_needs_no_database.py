"""The shared fixtures must not require a database that the test does not.

`_auth_users_table` in conftest.py is session-scoped and autouse, so it runs
before EVERY test in the suite -- including the many that touch no database at
all. `tests/test_rls_context.py` is the clearest case: four tests built
entirely from MagicMock, which have always passed in CI, and CI has no
Postgres service at all (see .github/workflows/backend-ci.yml -- it sets
DATABASE_URL but starts nothing to serve it).

An unguarded `engine.begin()` in that fixture turned all four into ERRORs on
this branch's first CI run:

    ERROR tests/test_rls_context.py::test_after_begin_applies_..._context
    sqlalchemy.exc.OperationalError: connection to server at "127.0.0.1",
    port 5432 failed: Connection refused

A fixture nothing in that file asked for, failing for a reason that file does
not care about. The fixture now swallows OperationalError; a test that
genuinely needs the database still fails on its own connection, with its own
message, exactly as it did before the fixture existed.
"""

import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent

#: Test files that must pass with nothing listening on the database port.
#: This is what CI actually runs (`pytest tests/test_rls_context.py -q`).
HERMETIC = ["tests/test_rls_context.py"]


def test_the_hermetic_tests_pass_with_no_database_reachable():
    """Run them in a subprocess pointed at a dead port, as CI effectively does.

    A subprocess rather than monkeypatching the engine, because the failure
    being guarded against happens at fixture setup in a fresh interpreter --
    which is the only place it can be reproduced honestly.
    """
    env = {
        **_clean_env(),
        # Nothing listens here. Port 1 is reserved and unbindable in practice.
        "DATABASE_URL": "postgresql+psycopg://nobody:nobody@127.0.0.1:1/nothing",
    }
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *HERMETIC],
        cwd=BACKEND, env=env, capture_output=True, text=True, timeout=300,
    )
    assert result.returncode == 0, (
        "tests that need no database failed when none was reachable.\n"
        "The conftest fixtures are requiring a database the test does not.\n\n"
        + result.stdout[-3000:] + result.stderr[-2000:]
    )


def _clean_env() -> dict:
    """The parent environment, with a SECRET_KEY so settings can be built.

    DATABASE_URL is set by the caller and a real environment variable takes
    precedence over anything in a .env file, which is what makes the dead port
    stick.
    """
    import os

    env = dict(os.environ)
    env.setdefault("SECRET_KEY", "test-only-not-a-real-secret-0123456789ab")
    return env
