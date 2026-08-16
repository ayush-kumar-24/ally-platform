"""Verifies the access token Supabase Auth issues to the frontend.

The frontend signs the founder in against Supabase directly -- an emailed OTP on
first use, their password afterwards -- and gets back a JWT; we only ever verify
it. Passwords are stored and checked by Supabase, so this backend still handles
no credentials and needs no login or callback routes of its own.

Which flow produced the token is invisible here, and deliberately so: it is
verified by signature and claims alone, so adding or removing a sign-in method
never touches this file.

Two signing schemes exist, and which one a project uses is not a detail we get
to choose:

  ES256 (asymmetric, current)  Supabase signs with a private key and publishes
      the public half as a JWKS. This is what a real Google/LinkedIn login
      produces today. We fetch the JWKS, match the token's `kid`, and verify
      against the public key -- so this backend never needs a shared secret.

  HS256 (legacy, shared secret)  Older projects signed user tokens with the
      project's JWT secret. It still signs the anon/service keys everywhere, so
      it is kept as a fallback rather than removed.

Why both: verifying the anon key against SUPABASE_JWT_SECRET tells you the
secret is correct and tells you *nothing* about user tokens -- on an asymmetric
project they are signed by an entirely different key. Accepting only HS256
therefore fails every real login with a 401 that looks like a bad secret.
"""

import threading
import time

import httpx
from jose import JWTError, jwt

from app.core.auth.base import AuthError, AuthProvider, AuthUser
from app.core.logger import logger

# A token whose `kid` we have never seen means the project rotated its signing
# key, so the JWKS is refetched. Bounded, because an attacker sending garbage
# `kid`s must not be able to turn each 401 into an outbound request.
_JWKS_MIN_REFRESH_SECONDS = 60
_JWKS_TIMEOUT_SECONDS = 5
_ASYMMETRIC_ALGORITHMS = ("ES256", "RS256")


class SupabaseAuthProvider(AuthProvider):
    name = "supabase"

    def __init__(
        self,
        jwt_secret: str = "",
        supabase_url: str = "",
        audience: str = "authenticated",
    ):
        if not jwt_secret and not supabase_url:
            raise RuntimeError(
                "Supabase auth needs SUPABASE_URL (for asymmetric ES256 tokens, "
                "which is what real logins use) or SUPABASE_JWT_SECRET (legacy "
                "HS256). Set at least one in your .env."
            )
        self._secret = jwt_secret
        self._jwks_url = (
            f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
            if supabase_url
            else ""
        )
        self._audience = audience
        self._keys: dict[str, dict] = {}
        self._fetched_at = 0.0
        self._lock = threading.Lock()

    # --- JWKS ---------------------------------------------------------------

    def _refresh_keys(self) -> None:
        """Refetch the JWKS, at most once per _JWKS_MIN_REFRESH_SECONDS."""
        with self._lock:
            if time.monotonic() - self._fetched_at < _JWKS_MIN_REFRESH_SECONDS:
                return
            try:
                response = httpx.get(self._jwks_url, timeout=_JWKS_TIMEOUT_SECONDS)
                response.raise_for_status()
                keys = response.json().get("keys", [])
            except (httpx.HTTPError, ValueError) as exc:
                # Keep whatever is cached: a transient network blip should not
                # sign everyone out mid-session.
                logger.warning("JWKS fetch failed", extra={"error": str(exc)})
                return
            self._keys = {k["kid"]: k for k in keys if k.get("kid")}
            self._fetched_at = time.monotonic()

    def _key_for(self, kid: str | None) -> dict:
        if not self._jwks_url:
            raise AuthError("Token is asymmetrically signed but SUPABASE_URL is not set")
        if not kid:
            raise AuthError("Token header has no key id")
        key = self._keys.get(kid)
        if key is None:
            self._refresh_keys()          # rotated key, or first use
            key = self._keys.get(kid)
        if key is None:
            raise AuthError("Token signed by an unknown key")
        return key

    # --- verification -------------------------------------------------------

    def verify_token(self, token: str | None) -> AuthUser:
        if not token:
            raise AuthError("Missing bearer token")

        try:
            header = jwt.get_unverified_header(token)
        except JWTError as exc:
            raise AuthError("Malformed token") from exc

        algorithm = header.get("alg")
        if algorithm in _ASYMMETRIC_ALGORITHMS:
            key: dict | str = self._key_for(header.get("kid"))
            algorithms = [algorithm]
        elif algorithm == "HS256":
            if not self._secret:
                raise AuthError("Token is HS256 but SUPABASE_JWT_SECRET is not set")
            key, algorithms = self._secret, ["HS256"]
        else:
            # Never let an unrecognised alg through -- notably "none".
            raise AuthError(f"Unsupported token algorithm {algorithm!r}")

        try:
            claims = jwt.decode(
                token,
                key,
                algorithms=algorithms,
                audience=self._audience,
                # Without require_aud, a token that simply omits `aud` skips the
                # audience check entirely and is accepted. Same for exp: a token
                # with no expiry would never go stale. Demand both.
                options={"require_aud": True, "require_exp": True, "require_sub": True},
            )
        except JWTError as exc:
            # Deliberately vague to the caller -- the detail goes to logs, not the client.
            logger.warning(
                "Supabase token rejected", extra={"error": str(exc), "alg": algorithm}
            )
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
