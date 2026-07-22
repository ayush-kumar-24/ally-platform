from pydantic import BaseModel, ConfigDict, Field


class IdentityOut(BaseModel):
    """Who the token belongs to."""

    id: str
    email: str | None = None
    provider: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access-token lifetime in seconds")


class SessionResponse(TokenPair):
    """Returned by /auth/session: the freshly minted token pair plus identity."""

    founder: IdentityOut
    provisioned: bool = Field(
        default=False,
        description="Whether a founder row was created/ensured. False while provisioning is disabled.",
    )


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refresh_token: str


class LogoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refresh_token: str


class AuthStatus(BaseModel):
    provider: str = Field(description="Active identity provider: dev | supabase")
    token_model: str = Field(description="Who issues the API token")
    access_token_ttl_seconds: int
    refresh_token_ttl_seconds: int
    provisioning_enabled: bool
