"""Request models for the Privacy Center endpoints. `extra="forbid"` fails closed."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class RestrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Art 18 restriction is a pause, not a termination -- it must be liftable, so
    # the same endpoint accepts false to resume.
    restricted: bool = True


class ConfirmRequest(BaseModel):
    """Body for the irreversible-ish actions.

    `confirm` must be explicitly true. A destructive right should never fire from an
    empty POST -- a stray request, a retried fetch or a prefetching client must not
    be able to schedule someone's erasure by accident.
    """

    model_config = ConfigDict(extra="forbid")

    confirm: bool = False
