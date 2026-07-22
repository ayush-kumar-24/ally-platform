from jose import JWTError, jwt

from app.core.auth.base import AuthError, AuthProvider, AuthUser


class SupabaseAuthProvider(AuthProvider):
    """Verifies the access token Supabase Auth issues to the frontend.

    The frontend does the Google/LinkedIn OAuth dance with Supabase directly and
    gets back a JWT; we only ever verify it. That means no password handling,
    no session storage, and no OAuth callback routes on our side.

    Supabase signs these with the project's JWT secret (HS256) and sets
    aud="authenticated" for signed-in users.
    """

    name = "supabase"

    def __init__(self, jwt_secret: str, audience: str = "authenticated"):
        if not jwt_secret:
            raise RuntimeError(
                "SUPABASE_JWT_SECRET is not set. Copy it from the Supabase dashboard "
                "(Project Settings -> API -> JWT Settings) into your .env."
            )
        self._secret = jwt_secret
        self._audience = audience

    def verify_token(self, token: str | None) -> AuthUser:
        if not token:
            raise AuthError("Missing bearer token")

        try:
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=["HS256"],
                audience=self._audience,
                # Without require_aud, a token that simply omits `aud` skips the
                # audience check entirely and is accepted. Same for exp: a token
                # with no expiry would never go stale. Demand both.
                options={"require_aud": True, "require_exp": True, "require_sub": True},
            )
        except JWTError as exc:
            # Deliberately vague to the caller -- the detail goes to logs, not the client.
            raise AuthError("Invalid or expired token") from exc

        founder_id = claims.get("sub")
        if not founder_id:
            raise AuthError("Token has no subject")

        return AuthUser(
            id=founder_id,
            email=claims.get("email"),
            provider=self.name,
            claims=claims,
        )
