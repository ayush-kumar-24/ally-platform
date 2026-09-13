"""The backend reads one .env, and reads the same one from any directory.

Both readers -- load_dotenv() in app.main and env_file= in app.core.config --
used to be given the bare relative name ".env", which resolves against the
current working directory. Started from the repository root, both read a
repo-root .env and backend/.env was never opened: no error, no log line, just
different values than the file you edited. These tests pin the fix.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.paths import BACKEND_DIR, ENV_FILE, ENV_EXAMPLE, stray_env_files


def test_env_file_is_absolute():
    """A relative path is the bug: it would resolve against the caller's cwd."""
    assert ENV_FILE.is_absolute()


def test_env_file_is_backend_dot_env():
    assert ENV_FILE == BACKEND_DIR / ".env"
    assert (BACKEND_DIR / "app" / "main.py").exists(), (
        "BACKEND_DIR no longer points at the backend package root -- the "
        "parents[] index in app/core/paths.py needs updating"
    )


def test_env_file_does_not_move_with_the_working_directory(tmp_path, monkeypatch):
    """The whole point: cwd must not decide which file is read."""
    monkeypatch.chdir(tmp_path)
    from importlib import reload

    from app.core import paths

    reload(paths)
    assert paths.ENV_FILE == BACKEND_DIR / ".env"


def test_settings_bind_the_resolved_env_file():
    """app.core.config must use ENV_FILE, not a bare relative ".env"."""
    from app.core.config import Settings

    env_file = Settings.model_config.get("env_file")
    assert env_file is not None
    assert Path(env_file).is_absolute()
    assert Path(env_file) == ENV_FILE


def test_main_loads_the_resolved_env_file():
    """load_dotenv() must be handed ENV_FILE, and before any app import."""
    source = (BACKEND_DIR / "app" / "main.py").read_text(encoding="utf-8")
    assert "load_dotenv(ENV_FILE, override=True)" in source, (
        "app/main.py must load ENV_FILE explicitly; a bare load_dotenv() "
        "searches upward from the working directory instead"
    )


def test_a_bare_relative_env_file_would_have_followed_the_cwd(tmp_path, monkeypatch):
    """Demonstrates the defect this module guards against, so the guard above
    is not merely asserting its own implementation."""

    class Relative(BaseSettings):
        model_config = SettingsConfigDict(env_file=".env", extra="ignore")
        PROBE: str = "not found"

    class Absolute(BaseSettings):
        model_config = SettingsConfigDict(env_file=tmp_path / "a" / ".env",
                                          extra="ignore")
        PROBE: str = "not found"

    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    (tmp_path / "a" / ".env").write_text("PROBE=intended\n", encoding="utf-8")
    (tmp_path / "b" / ".env").write_text("PROBE=wrong_directory\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path / "b")
    assert Relative().PROBE == "wrong_directory"   # the bug
    assert Absolute().PROBE == "intended"          # the fix


def test_example_file_is_never_reported_as_a_stray():
    """.env.example is committed on purpose and must not be flagged."""
    assert ENV_EXAMPLE.name not in stray_env_files()
    assert ENV_EXAMPLE.exists(), ".env.example documents every supported variable"


def test_stray_env_files_finds_inert_neighbours(tmp_path, monkeypatch):
    from app.core import paths

    monkeypatch.setattr(paths, "BACKEND_DIR", tmp_path)
    monkeypatch.setattr(paths, "ENV_FILE", tmp_path / ".env")
    monkeypatch.setattr(paths, "ENV_EXAMPLE", tmp_path / ".env.example")
    for name in (".env", ".env.example", ".env.rds", ".env.bak_OCR"):
        (tmp_path / name).write_text("X=1\n", encoding="utf-8")

    found = paths.stray_env_files()
    assert found == [".env.bak_OCR", ".env.rds"]
    assert ".env" not in found, "the file that IS loaded is not a stray"
    assert ".env.example" not in found


def test_stray_env_files_survives_an_unreadable_directory(monkeypatch):
    """Boot must never fail because this diagnostic could not run."""
    from app.core import paths

    class Exploding:
        def glob(self, _pattern):
            raise OSError("permission denied")

    monkeypatch.setattr(paths, "BACKEND_DIR", Exploding())
    assert paths.stray_env_files() == []
