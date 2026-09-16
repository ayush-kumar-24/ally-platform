"""Where this backend's files live, resolved from this file -- not from the
current working directory.

THE ONE .env. This backend reads exactly one environment file, `backend/.env`,
and it is found the same way no matter where the process was started from.

That was not true before. Two places load it -- `load_dotenv()` in app.main and
`env_file=".env"` in app.core.config -- and both were given the bare relative
name ".env", which resolves against the current working directory. Started from
`backend/`, both read `backend/.env`. Started from the repository root (which is
what `uvicorn backend.app.main:app` and a Docker image with a repo-root WORKDIR
do), both read a repo-root `.env` instead and `backend/.env` is never opened --
no error, no log line, just different values. Measured, not assumed: the same
probe returned FROM_REPO_ROOT_ENV from one directory and FROM_BACKEND_ENV from
the other.

A file that is loaded or not depending on the directory someone typed a command
in is the kind of thing that gets diagnosed as a bad API key (see the
load_dotenv comment in app/main.py for the last time that happened).

ENV_FILE is absolute, so both readers now open the same file always.

NOTHING ELSE IS READ. `.env.rds`, `.env.bak_OCR`, `.env.local` and any other
`.env.*` sitting next to it are inert -- no code path in this repository opens
them. They are not a fallback and not a profile; the only way one of them takes
effect is a human copying it over `.env`. `stray_env_files()` finds them so boot
can say so out loud, because a stale alternate next to the live file is a
footgun that looks like configuration.
"""

from __future__ import annotations

from pathlib import Path

#: `backend/` -- this file is backend/app/core/paths.py.
BACKEND_DIR = Path(__file__).resolve().parents[2]

#: The single environment file this backend reads. Absolute, so the working
#: directory cannot change which file that is.
ENV_FILE = BACKEND_DIR / ".env"

#: Committed as documentation of every supported variable. Never loaded.
ENV_EXAMPLE = BACKEND_DIR / ".env.example"


def stray_env_files() -> list[str]:
    """Names of `.env.*` files next to ENV_FILE that nothing reads.

    `.env.example` is excluded -- it is meant to be there. Everything else is
    a backup, an alternate deployment's values, or a leftover, and is reported
    at boot so it cannot be mistaken for live configuration.
    """
    try:
        return sorted(
            p.name
            for p in BACKEND_DIR.glob(".env.*")
            if p.is_file() and p.name != ENV_EXAMPLE.name
        )
    except OSError:  # unreadable directory must never stop the app booting
        return []
