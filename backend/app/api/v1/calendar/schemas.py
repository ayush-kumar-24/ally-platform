"""Wire shapes for the calendar endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CalendarStatusResponse(BaseModel):
    connected: bool
    provider: str = "google"
    account_email: str = Field(
        default="",
        description="The Google account connected. Need not match the Ally "
                    "login, which is email-only and unrelated.")
    status: str = Field(default="disconnected",
                        description="active | revoked | error | disconnected")
    needs_reconnect: bool = False
    last_error: str = ""
    available: bool = Field(
        default=False,
        description="Whether this deployment can offer calendar sync at all "
                    "(OAuth client configured and a token encryption key set).")


class CalendarConnectStart(BaseModel):
    authorization_url: str


class DisconnectResult(BaseModel):
    disconnected: bool
    message: str
