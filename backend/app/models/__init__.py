"""SQLAlchemy models -- all 56 logical tables of the existing schema.

- `schema.py`      -- 53 non-partitioned tables, generated from the live database
                      (sqlacodegen) then curated: rewired onto the app Base,
                      pgvector columns typed, the auth.users FK dropped (Supabase
                      owns that schema).
- `partitioned.py` -- messages / analytics_events / audit_logs, hand-modelled
                      because the generator skips partitioned parents.

Importing this package registers every table on `Base.metadata`, which is what
Alembic reads. The database is the source of truth: a model here must match its
table, or `alembic revision --autogenerate` will report drift. Regenerate rather
than hand-edit when the schema changes.

Class names follow sqlacodegen's convention (pluralised: `Founders`,
`Conversations`). `Founder` is aliased to `Founders` for existing call sites.
"""

from app.models import partitioned, schema
from app.models.partitioned import AnalyticsEvent, AuditLog, Message
from app.models.schema import Founders

# Existing code (api/deps.py, profile routes) refers to `Founder`.
Founder = Founders

__all__ = [
    "schema",
    "partitioned",
    "Founder",
    "Founders",
    "Message",
    "AnalyticsEvent",
    "AuditLog",
]
