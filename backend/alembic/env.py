from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings
from app.db.session import Base

# Importing the models package registers every model on Base.metadata.
# Without this import Alembic sees empty metadata and concludes that every
# table in the database has been deleted.
import app.models  # noqa: F401

config = context.config

# The URL comes from .env, never from alembic.ini -- alembic.ini gets committed,
# .env does not. This is also the single value that changes for AWS RDS later.
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Supabase owns these. Alembic must never emit DDL against them.
IGNORED_SCHEMAS = {
    "auth",
    "storage",
    "realtime",
    "graphql",
    "graphql_public",
    "extensions",
    "vault",
    "net",
    "supabase_migrations",
    "supabase_functions",
    "cron",
    "pgsodium",
    "pgsodium_masks",
}


# Objects that exist in the database but not in our models are left alone
# rather than dropped. Indexes and constraints are in this set for the same
# reason tables are: the Supabase migrations created several that our models do
# not declare, and without this the first autogenerate against a *modelled*
# table emits DROP INDEX / DROP CONSTRAINT for all of them -- including
# founders_user_id_fkey, the FK binding founders to auth.users.
ADOPT_NOT_MANAGE = {
    "table",
    "index",
    "foreign_key_constraint",
    "unique_constraint",
}


def include_object(object, name, type_, reflected, compare_to):
    """Decide whether autogenerate may touch a given database object.

    Three protections, all of which matter when adopting an existing database:

    1. Anything outside `public` is off-limits -- those are Supabase's own
       schemas, and generating DDL against them would break the project.
    2. Anything that exists in the database but not in our models is ignored
       (`reflected and compare_to is None`). We are adopting a database of 56
       tables created by Supabase migrations; without this the first
       autogenerate would emit DROP TABLE for every one of them.
    3. That same rule covers indexes and constraints, not just tables -- see
       ADOPT_NOT_MANAGE above.

    The trade-off is deliberate: an index genuinely removed from a model will
    not be auto-dropped, so removals must be written by hand. That is the right
    way round -- a missed drop is an annoyance, an unwanted one is an outage.

    Columns are intentionally NOT in ADOPT_NOT_MANAGE, so adding a column to a
    model still produces a migration. That is the normal path for schema change.

    Note what Alembic still cannot see at all: RLS policies, partition layouts,
    and database functions. Those stay Supabase-managed -- do not expect
    autogenerate to reproduce or preserve them.
    """
    schema = getattr(object, "schema", None)
    if schema in IGNORED_SCHEMAS:
        return False

    if type_ in ADOPT_NOT_MANAGE and reflected and compare_to is None:
        return False

    return True


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of running it -- useful for reviewing DDL."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        include_schemas=False,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            include_schemas=False,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
