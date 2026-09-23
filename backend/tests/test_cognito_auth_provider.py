"""CognitoAuthProvider -- the code that decides who you are.

WHY THIS FILE EXISTS. This provider is what stands between a stranger and
every founder's account once AUTH_PROVIDER=cognito, and until now no test had
ever executed a line of it. test_auth.py covers the Supabase path only, so the
whole Cognito path was going to be exercised for the first time in production,
on the day of the cutover.

The cases below are the ones where a mistake does not look like a bug. A
provider that accepts an unsigned token, or a token from another app's user
pool, or an ACCESS token where an ID token is required, serves pages perfectly
and authenticates the wrong person. Nothing fails, nothing logs, and the first
sign is somebody seeing data that is not theirs.

Everything is signed with a throwaway key generated here, and the JWKS endpoint
is faked. No network, no AWS account, no Cognito pool.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwk, jwt

from app.core.auth.base import AuthError
from app.core.auth.cognito_provider import CognitoAuthProvider

REGION = "ap-south-1"
POOL = "ap-south-1_TESTPOOL"
CLIENT = "test-client-id"
ISSUER = f"https://cognito-idp.{REGION}.amazonaws.com/{POOL}"
KID = "test-key-1"


def _keypair():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return private_pem, public_pem


def _jwk_for(public_pem: str, kid: str) -> dict:
    entry = jwk.construct(public_pem, "RS256").to_dict()
    return {
        k: (v.decode() if isinstance(v, bytes) else v)
        for k, v in entry.items()
    } | {"kid": kid, "use": "sig"}


@pytest.fixture
def keys():
    private_pem, public_pem = _keypair()
    return {"private": private_pem, "jwk": _jwk_for(public_pem, KID)}


@pytest.fixture
def jwks_server(monkeypatch):
    """Stand in for Cognito's /.well-known/jwks.json and count the calls, so a
    test can assert the keys were re-fetched -- or that they were not."""
    state = {"keys": [], "calls": 0, "fail": False}

    class _Response:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    def fake_get(url, timeout=None):
        state["calls"] += 1
        if state["fail"]:
            import httpx
            raise httpx.ConnectError("jwks unreachable")
        return _Response({"keys": state["keys"]})

    import app.core.auth.cognito_provider as module
    monkeypatch.setattr(module.httpx, "get", fake_get)
    return state


@pytest.fixture
def provider(jwks_server, keys):
    jwks_server["keys"] = [keys["jwk"]]
    return CognitoAuthProvider(region=REGION, user_pool_id=POOL, client_id=CLIENT)


def _token(keys, *, kid=KID, algorithm="RS256", key=None, **overrides):
    now = datetime.now(timezone.utc)
    claims = {
        "sub": "cognito-sub-123",
        "email": "founder@example.com",
        "email_verified": True,
        "token_use": "id",
        "aud": CLIENT,
        "iss": ISSUER,
        "exp": int((now + timedelta(minutes=5)).timestamp()),
        "iat": int(now.timestamp()),
    }
    claims.update(overrides)
    return jwt.encode(claims, key or keys["private"], algorithm=algorithm,
                      headers={"kid": kid})


# --- the happy path ---------------------------------------------------------

def test_a_valid_id_token_identifies_the_founder(provider, keys):
    user = provider.verify_token(_token(keys))
    assert user.id == "cognito-sub-123"
    assert user.email == "founder@example.com"
    assert user.provider == "cognito"
    assert user.claims["token_use"] == "id"


def test_email_verified_as_the_string_true_is_accepted(provider, keys):
    """Cognito serialises this as a string in some flows and a boolean in
    others. Refusing the string would lock out real, verified founders."""
    assert provider.verify_token(_token(keys, email_verified="true"))


# --- tokens that must be refused --------------------------------------------

@pytest.mark.parametrize("token", [None, ""])
def test_no_token_is_refused(provider, token):
    with pytest.raises(AuthError):
        provider.verify_token(token)


def test_garbage_is_refused(provider):
    with pytest.raises(AuthError):
        provider.verify_token("not-a-jwt")


def test_an_access_token_is_refused_where_an_id_token_is_required(provider, keys):
    """THE case worth having. An access token from the same pool is signed by
    the same key and passes every signature, audience and issuer check -- it
    simply carries no email. Accepting it would mean provisioning founders with
    no address, or matching them to the wrong one."""
    token = _token(keys, token_use="access")
    with pytest.raises(AuthError, match="ID token"):
        provider.verify_token(token)


def test_a_token_from_another_app_client_is_refused(provider, keys):
    with pytest.raises(AuthError):
        provider.verify_token(_token(keys, aud="someone-elses-client"))


def test_a_token_from_another_user_pool_is_refused(provider, keys):
    """Same algorithm, same shape, different pool. Without the issuer check any
    Cognito pool in any AWS account would be able to mint our sessions."""
    other = f"https://cognito-idp.{REGION}.amazonaws.com/ap-south-1_OTHERPOOL"
    with pytest.raises(AuthError):
        provider.verify_token(_token(keys, iss=other))


def test_an_expired_token_is_refused(provider, keys):
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    with pytest.raises(AuthError):
        provider.verify_token(_token(keys, exp=int(past.timestamp())))


def test_a_token_signed_by_an_unknown_key_is_refused(provider, keys):
    stranger_private, _ = _keypair()
    token = _token(keys, key=stranger_private)
    with pytest.raises(AuthError):
        provider.verify_token(token)


def test_a_token_with_no_key_id_is_refused(provider, keys):
    with pytest.raises(AuthError, match="key id"):
        provider.verify_token(_token(keys, kid=None))


def test_an_hs256_token_is_refused_even_with_the_right_claims(provider):
    """Algorithm confusion, the classic JWT attack: sign with HS256 using the
    PUBLIC key as the shared secret and a naive verifier accepts it. The
    provider pins RS256 from the header before it looks anything up, so this
    dies early -- this test exists to make sure it stays that way."""
    now = datetime.now(timezone.utc)
    forged = jwt.encode(
        {"sub": "attacker", "email": "attacker@example.com", "email_verified": True,
         "token_use": "id", "aud": CLIENT, "iss": ISSUER,
         "exp": int((now + timedelta(minutes=5)).timestamp())},
        "any-shared-secret", algorithm="HS256", headers={"kid": KID},
    )
    with pytest.raises(AuthError, match="algorithm"):
        provider.verify_token(forged)


def test_an_unverified_email_is_refused(provider, keys):
    with pytest.raises(AuthError, match="not verified"):
        provider.verify_token(_token(keys, email_verified=False))


def test_a_token_with_no_email_is_refused(provider, keys):
    token = _token(keys)
    # Rebuild without the claim rather than blanking it, which is what a pool
    # configured without the email scope actually produces.
    claims = jwt.get_unverified_claims(token)
    claims.pop("email")
    stripped = jwt.encode(claims, keys["private"], algorithm="RS256",
                          headers={"kid": KID})
    with pytest.raises(AuthError, match="email"):
        provider.verify_token(stripped)


# --- key rotation and the JWKS cache ----------------------------------------

def test_a_rotated_key_is_fetched_rather_than_rejected(provider, jwks_server, keys):
    """Cognito rotates signing keys. A provider that caches once and never
    looks again starts refusing every token, hours after the last deploy, with
    nothing having changed on our side."""
    provider.verify_token(_token(keys))
    calls_before = jwks_server["calls"]

    new_private, new_public = _keypair()
    jwks_server["keys"] = [_jwk_for(new_public, "test-key-2")]
    # The throttle must not stop a genuinely unknown kid from being looked up.
    provider._fetched_at = time.monotonic() - 120

    user = provider.verify_token(
        _token({"private": new_private}, kid="test-key-2")
    )
    assert user.id == "cognito-sub-123"
    assert jwks_server["calls"] > calls_before


def test_the_cache_is_not_refetched_for_every_request(provider, jwks_server, keys):
    """One JWKS fetch per minute at most. Without the throttle, a burst of
    tokens carrying an unknown kid is a burst of outbound requests."""
    for _ in range(5):
        provider.verify_token(_token(keys))
    assert jwks_server["calls"] == 1


def test_an_unreachable_jwks_endpoint_refuses_rather_than_crashes(jwks_server, keys):
    # Keys are present but unreachable, so the refusal is caused by the failed
    # fetch rather than by an empty fixture -- which would pass for the wrong
    # reason and keep passing if the error handling were removed.
    jwks_server["keys"] = [keys["jwk"]]
    jwks_server["fail"] = True
    provider = CognitoAuthProvider(region=REGION, user_pool_id=POOL, client_id=CLIENT)
    with pytest.raises(AuthError):
        provider.verify_token(_token(keys))


def test_keys_are_fetched_on_the_first_request_of_a_fresh_process(
    monkeypatch, jwks_server, keys
):
    """A FRESH CONTAINER IS THE CASE THIS GUARDS. The throttle compares against
    time.monotonic(), which on a newly booted Fargate microVM starts near zero.
    With `_fetched_at` initialised to 0.0, the very first fetch looked like one
    that had just happened, so it was skipped -- and every token was rejected as
    signed by an unknown key until the process had been alive a minute.

    Pinning monotonic low reproduces that exact start-up window.
    """
    import app.core.auth.cognito_provider as module
    monkeypatch.setattr(module.time, "monotonic", lambda: 5.0)

    jwks_server["keys"] = [keys["jwk"]]
    provider = CognitoAuthProvider(region=REGION, user_pool_id=POOL, client_id=CLIENT)
    assert provider.verify_token(_token(keys)).id == "cognito-sub-123"
    assert jwks_server["calls"] == 1


# --- configuration -----------------------------------------------------------

@pytest.mark.parametrize("kwargs", [
    {"region": "", "user_pool_id": POOL, "client_id": CLIENT},
    {"region": REGION, "user_pool_id": "", "client_id": CLIENT},
    {"region": REGION, "user_pool_id": POOL, "client_id": ""},
])
def test_missing_configuration_refuses_to_construct(kwargs):
    """Loudly, at start-up. A provider built with a blank client id would
    accept any audience, which is the quietest possible way to be wrong."""
    with pytest.raises(RuntimeError):
        CognitoAuthProvider(**kwargs)
