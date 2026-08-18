from pydantic import BaseModel, ConfigDict, Field


class IdentityOut(BaseModel):
    """Who the token belongs to."""

    id: str
    email: str | None = None
    provider: str


class TokenPair(BaseModel):
    access_token: str
    # Deliberately absent from the response body -- the refresh token is
    # delivered ONLY via the HttpOnly ally_refresh_token cookie (see
    # REFRESH_COOKIE_* in core/config.py and _set_refresh_cookie in
    # api/v1/auth/routes.py). Kept as an optional field rather than removed
    # outright so a future non-browser client (one that genuinely cannot
    # use a cookie jar) has a documented place to receive it, without that
    # path being what a browser client accidentally uses -- nothing here
    # ever populates it.
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int = Field(description="Access-token lifetime in seconds")


class SessionResponse(TokenPair):
    """Returned by /auth/session: the freshly minted token pair plus identity."""

    founder: IdentityOut
    provisioned: bool = Field(
        default=False,
        description=(
            "True only when THIS call created the founder row -- i.e. a genuine "
            "first login. False for every returning login, for dev identities "
            "(never provisioned), and while provisioning is disabled. The old "
            "wording, 'created/ensured', is what let this report true for "
            "founders that had existed for days."
        ),
    )


class RefreshRequest(BaseModel):
    """Body is optional -- a browser client sends none at all and relies on
    the ally_refresh_token cookie riding along automatically. `refresh_token`
    here is the fallback for a caller that cannot use cookies."""

    model_config = ConfigDict(extra="forbid")
    refresh_token: str | None = None


class LogoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refresh_token: str | None = None


class AuthStatus(BaseModel):
    provider: str = Field(description="Active identity provider: dev | supabase")
    token_model: str = Field(description="Who issues the API token")
    access_token_ttl_seconds: int
    refresh_token_ttl_seconds: int
    provisioning_enabled: bool
