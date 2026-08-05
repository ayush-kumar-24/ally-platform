# Production image for AWS App Runner (or any container host).
#
# NOT scripts/run_dev.py -- that exists only to chdir so a local .env resolves
# (see its own docstring). A hosted environment supplies configuration as real
# env vars, so this runs uvicorn directly, and --reload is off: reload spawns
# a second process, which would double every Supabase connection this pool
# already opens.

FROM python:3.11-slim

# requirements.txt already pins psycopg-binary, which ships a compiled libpq --
# no system Postgres headers or a C toolchain needed to install it, so there is
# nothing to apt-get here.
WORKDIR /app

# Dependencies first, so a code-only change doesn't invalidate this layer.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Runs as the container's own user, not root -- App Runner has no opinion on
# this, but there's no reason to run a network-facing process as root either.
RUN useradd --create-home --shell /bin/bash ally
USER ally

EXPOSE 8000

# Migrations run on every start. Idempotent (alembic no-ops if the schema is
# current) and this is a single-instance-class beta deploy, so there is no
# concurrent-migration race to worry about yet -- revisit if this ever scales
# to multiple instances deploying at once.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
