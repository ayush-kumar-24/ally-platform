"""Amazon Cognito upstream identity verification for /auth/session."""

import threading
import time

import httpx
from jose import JWTError, jwt

from app.core.auth.base import AuthError, AuthProvider, AuthUser
from app.core.logger import logger


_JWKS_MIN_REFRESH_SECONDS = 60
_JWKS_TIMEOUT_SECONDS = 5


class CognitoAuthProvider(AuthProvider):
    name = "cognito"

    def __init__(
        self,
        region: str,
        user_pool_id: str,
        client_id: str,
    ):
        if not region or not user_pool_id or not client_id:
            raise RuntimeError(
                "Cognito auth requires COGNITO_REGION, "
                "COGNITO_USER_POOL_ID and COGNITO_CLIENT_ID"
            )

        self._client_id = client_id
        self._issuer = (
            f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"
        )
        self._jwks_url = f"{self._issuer}/.well-known/jwks.json"

        self._keys: dict[str, dict] = {}
        #: None until the first successful fetch, and NOT 0.0. The throttle
        #: below compares against time.monotonic(), whose zero point is
        #: arbitrary -- on a freshly booted Fargate microVM it starts near
        #: zero. With 0.0 as the initial value, the very first fetch looked
        #: like one that had just happened and was skipped, so every token was
        #: rejected as "signed by an unknown Cognito key" until the process had
        #: been alive a minute. A sentinel that cannot be mistaken for a
        #: timestamp is the fix; `test_keys_are_fetched_on_the_first_request_
        #: of_a_fresh_process` is what keeps it.
        self._fetched_at: float | None = None
        self._lock = threading.Lock()

    def _refresh_keys(self) -> None:
        with self._lock:
            if (
                self._fetched_at is not None
                and time.monotonic() - self._fetched_at < _JWKS_MIN_REFRESH_SECONDS
            ):
                return

            try:
                response = httpx.get(
                    self._jwks_url,
                    timeout=_JWKS_TIMEOUT_SECONDS,
                )
                response.raise_for_status()
                keys = response.json().get("keys", [])
            except (httpx.HTTPError, ValueError) as exc:
                logger.warning(
                    "Cognito JWKS fetch failed",
                    extra={"error": str(exc)},
                )
                return

            self._keys = {
                key["kid"]: key
                for key in keys
                if key.get("kid")
            }
            self._fetched_at = time.monotonic()

    def _key_for(self, kid: str | None) -> dict:
        if not kid:
            raise AuthError("Token header has no key id")

        key = self._keys.get(kid)

        if key is None:
            self._refresh_keys()
            key = self._keys.get(kid)

        if key is None:
            raise AuthError("Token signed by an unknown Cognito key")

        return key

    def verify_token(self, token: str | None) -> AuthUser:
        if not token:
            raise AuthError("Missing bearer token")

        try:
            header = jwt.get_unverified_header(token)
        except JWTError as exc:
            raise AuthError("Malformed token") from exc

        algorithm = header.get("alg")

        # Cognito user-pool JWTs are RS256 signed.
        if algorithm != "RS256":
            raise AuthError(
                f"Unsupported Cognito token algorithm {algorithm!r}"
            )

        key = self._key_for(header.get("kid"))

        try:
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience=self._client_id,
                issuer=self._issuer,
                options={
                    "require_aud": True,
                    "require_exp": True,
                    "require_sub": True,
                },
            )
        except JWTError as exc:
            logger.warning(
                "Cognito token rejected",
                extra={"error": str(exc)},
            )
            raise AuthError("Invalid or expired token") from exc

        # /auth/session uses the ID token because it carries email and
        # email_verified. Ally issues its own access/refresh tokens afterwards.
        if claims.get("token_use") != "id":
            raise AuthError("Expected Cognito ID token")

        subject = claims.get("sub")
        email = claims.get("email")
        email_verified = claims.get("email_verified")

        if not subject:
            raise AuthError("Token has no subject")

        if not email:
            raise AuthError("Token has no email")

        if email_verified is not True and str(email_verified).lower() != "true":
            raise AuthError("Email is not verified")

        return AuthUser(
            id=str(subject),
            email=str(email),
            provider=self.name,
            claims=claims,
        )