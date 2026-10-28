import base64
import time
import uuid

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.config import Settings
from app.services.auth import SupabaseJwtVerifier


def _encode(value: int) -> str:
    size = (value.bit_length() + 7) // 8
    return base64.urlsafe_b64encode(value.to_bytes(size, "big")).rstrip(b"=").decode()


@pytest.fixture
def signing_material():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    numbers = key.public_key().public_numbers()
    jwk = {
        "kty": "RSA",
        "kid": "test-key",
        "use": "sig",
        "alg": "RS256",
        "n": _encode(numbers.n),
        "e": _encode(numbers.e),
    }
    return key, jwk


def _token(key, **overrides):
    now = int(time.time())
    claims = {
        "iss": "https://project.supabase.co/auth/v1",
        "aud": "authenticated",
        "sub": str(uuid.uuid4()),
        "role": "authenticated",
        "email": "analyst@example.com",
        "is_anonymous": False,
        "iat": now,
        "exp": now + 300,
    }
    claims.update(overrides)
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test-key"})


def _verifier(jwk):
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, json={"keys": [jwk]}))
    client = httpx.AsyncClient(transport=transport)
    settings = Settings(
        app_env="test",
        database_url=None,
        supabase_url="https://project.supabase.co",
    )
    return SupabaseJwtVerifier(settings, client), client


@pytest.mark.asyncio
async def test_valid_supabase_token_is_verified(signing_material):
    key, jwk = signing_material
    verifier, client = _verifier(jwk)
    user = await verifier.verify(_token(key))
    assert user.email == "analyst@example.com"
    assert user.is_anonymous is False
    await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changes",
    [
        {"exp": 1},
        {"iss": "https://attacker.example/auth/v1"},
        {"aud": "wrong-audience"},
        {"role": "service_role"},
        {"sub": "not-a-uuid"},
    ],
)
async def test_invalid_claims_are_rejected(signing_material, changes):
    key, jwk = signing_material
    verifier, client = _verifier(jwk)
    with pytest.raises(Exception) as caught:
        await verifier.verify(_token(key, **changes))
    assert caught.value.status_code == 401
    assert "token" in caught.value.detail.lower()
    await client.aclose()


@pytest.mark.asyncio
async def test_malformed_and_unknown_key_tokens_are_rejected(signing_material):
    key, jwk = signing_material
    verifier, client = _verifier(jwk)
    with pytest.raises(Exception) as malformed:
        await verifier.verify("not-a-jwt")
    assert malformed.value.status_code == 401
    unknown = jwt.encode(
        jwt.decode(_token(key), options={"verify_signature": False}),
        key,
        algorithm="RS256",
        headers={"kid": "unknown"},
    )
    with pytest.raises(Exception) as missing_key:
        await verifier.verify(unknown)
    assert missing_key.value.status_code == 401
    await client.aclose()


@pytest.mark.asyncio
async def test_invalid_signature_for_known_key_is_rejected(signing_material):
    _key, jwk = signing_material
    attacker = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    verifier, client = _verifier(jwk)
    with pytest.raises(Exception) as caught:
        await verifier.verify(_token(attacker))
    assert caught.value.status_code == 401
    await client.aclose()


@pytest.mark.asyncio
async def test_unknown_key_refreshes_jwks_once_and_accepts_rotated_key(signing_material):
    old_key, old_jwk = signing_material
    new_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    numbers = new_key.public_key().public_numbers()
    new_jwk = {
        "kty": "RSA",
        "kid": "rotated-key",
        "use": "sig",
        "alg": "RS256",
        "n": _encode(numbers.n),
        "e": _encode(numbers.e),
    }
    calls = 0

    def jwks(_request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"keys": [old_jwk] if calls == 1 else [old_jwk, new_jwk]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(jwks))
    verifier = SupabaseJwtVerifier(
        Settings(app_env="test", database_url=None, supabase_url="https://project.supabase.co"),
        client,
    )
    await verifier.verify(_token(old_key))
    now = int(time.time())
    rotated = jwt.encode(
        {
            "iss": "https://project.supabase.co/auth/v1",
            "aud": "authenticated",
            "sub": str(uuid.uuid4()),
            "role": "authenticated",
            "is_anonymous": False,
            "iat": now,
            "exp": now + 300,
        },
        new_key,
        algorithm="RS256",
        headers={"kid": "rotated-key"},
    )
    user = await verifier.verify(rotated)
    assert user.id
    assert calls == 2
    await client.aclose()


@pytest.mark.asyncio
async def test_jwks_network_failure_is_sanitized():
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _request: httpx.Response(503, text="secret detail"))
    )
    verifier = SupabaseJwtVerifier(
        Settings(app_env="test", database_url=None, supabase_url="https://project.supabase.co"),
        client,
    )
    with pytest.raises(Exception) as caught:
        await verifier.verify("eyJhbGciOiJSUzI1NiIsImtpZCI6IngifQ.e30.signature")
    assert caught.value.status_code == 401
    assert "secret detail" not in caught.value.detail
    await client.aclose()
