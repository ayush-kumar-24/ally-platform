"""Request models for the consents endpoints.

`extra="forbid"` rejects unknown keys (fail closed). Note what is NOT accepted:
`consented_at`. The server stamps the time itself -- a client-supplied timestamp on
a legal record is unverifiable, so accepting one would weaken the evidence rather
than strengthen it.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ConsentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    terms_version: str = Field(max_length=20, examples=["1.0"])
    privacy_version: str = Field(max_length=20, examples=["1.0"])

    # Mandatory gate -- the service refuses to store a record when this is false.
    agree_terms: bool

    # Separate, unbundled opt-in. Defaults to false so an omitted field can never
    # be read as consent.
    agree_diagnosis: bool = False
