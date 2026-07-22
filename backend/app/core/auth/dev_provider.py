from app.core.auth.base import AuthProvider, AuthUser

# Fixed identity so local data stays stable across restarts.
DEV_FOUNDER_ID = "00000000-0000-0000-0000-000000000001"
DEV_FOUNDER_EMAIL = "dev@ally.local"


class DevAuthProvider(AuthProvider):
    """Local stand-in for real auth. Never reachable in production -- the
    factory in __init__.py refuses to build it when ENVIRONMENT=production.

    No token at all resolves to the default dev founder, so you can hit any
    protected route from /docs or curl without setting up a login flow.
    Passing any bearer token instead uses that string as the founder id, which
    is how you exercise multi-founder behaviour before real logins exist.
    """

    name = "dev"

    def verify_token(self, token: str | None) -> AuthUser:
        founder_id = token.strip() if token and token.strip() else DEV_FOUNDER_ID
        is_default = founder_id == DEV_FOUNDER_ID
        return AuthUser(
            id=founder_id,
            email=DEV_FOUNDER_EMAIL if is_default else f"{founder_id}@ally.local",
            provider=self.name,
            claims={"dev": True},
        )
