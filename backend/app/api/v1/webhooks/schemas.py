"""Request models for inbound webhooks."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SupabaseAuthWebhookPayload(BaseModel):
    """Shape of a Supabase Database Webhook firing on `auth.users` (configured as a
    DELETE trigger in the Supabase dashboard -- Database > Webhooks -- pointed at
    POST /api/v1/webhooks/supabase/auth-user-deleted with the shared secret header).

    Extra fields are allowed (not forbidden): Supabase's payload carries more than
    we read, and rejecting on an unrecognised field would break the first time
    Supabase adds one. `schema` is aliased because it shadows a BaseModel classmethod.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    type: str
    table: str | None = None
    schema_name: str | None = Field(default=None, alias="schema")
    record: dict[str, Any] | None = None
    old_record: dict[str, Any] | None = None
