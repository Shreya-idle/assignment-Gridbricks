import asyncio
import time
import uuid
from dataclasses import dataclass
from typing import Any

import httpx
import jwt
from fastapi import HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError, PyJWK

from app.core.config import Settings


@dataclass(frozen=True)
class AuthenticatedUser:
    id: uuid.UUID
    email: str | None
    is_anonymous: bool


class SupabaseJwtVerifier:
    """Verify Supabase access tokens with the project's rotating asymmetric JWKS."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.issuer = settings.supabase_jwt_issuer
        self.audience = settings.supabase_jwt_audience
        self.cache_seconds = settings.supabase_jwks_cache_seconds
        self._client = client or httpx.AsyncClient(timeout=10)
        self._owns_client = client is None
        self._keys: dict[str, PyJWK] = {}
        self._expires_at = 0.0
        self._lock = asyncio.Lock()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def verify(self, token: str) -> AuthenticatedUser:
        if self.issuer is None:
            raise _unauthorized("Authentication is not configured")
        try:
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
            algorithm = header.get("alg")
            if not isinstance(kid, str) or algorithm not in {"RS256", "ES256"}:
                raise InvalidTokenError("Unsupported token header")
            key = await self._get_key(kid)
            claims = jwt.decode(
                token,
                key.key,
                algorithms=[algorithm],
                issuer=self.issuer,
                audience=self.audience,
                options={"require": ["exp", "iat", "iss", "sub", "aud"]},
            )
            if claims.get("role") != "authenticated":
                raise InvalidTokenError("Unexpected role")
            subject = uuid.UUID(str(claims["sub"]))
            email = claims.get("email")
            if email is not None and not isinstance(email, str):
                raise InvalidTokenError("Invalid email claim")
            return AuthenticatedUser(
                id=subject,
                email=email,
                is_anonymous=claims.get("is_anonymous") is True,
            )
        except (InvalidTokenError, KeyError, TypeError, ValueError):
            raise _unauthorized("Invalid or expired access token") from None

    async def _get_key(self, kid: str) -> PyJWK:
        if time.monotonic() >= self._expires_at:
            await self._refresh_keys()
        key = self._keys.get(kid)
        if key is None:
            await self._refresh_keys(force=True)
            key = self._keys.get(kid)
        if key is None:
            raise InvalidTokenError("Unknown signing key")
        return key

    async def _refresh_keys(self, force: bool = False) -> None:
        async with self._lock:
            if not force and self._keys and time.monotonic() < self._expires_at:
                return
            try:
                response = await self._client.get(f"{self.issuer}/.well-known/jwks.json")
                response.raise_for_status()
                payload: Any = response.json()
                raw_keys = payload.get("keys") if isinstance(payload, dict) else None
                if not isinstance(raw_keys, list):
                    raise ValueError("Invalid JWKS")
                keys = {
                    item["kid"]: PyJWK.from_dict(item)
                    for item in raw_keys
                    if isinstance(item, dict) and isinstance(item.get("kid"), str)
                }
                if not keys:
                    raise ValueError("Empty JWKS")
                self._keys = keys
                self._expires_at = time.monotonic() + self.cache_seconds
            except (httpx.HTTPError, ValueError, InvalidTokenError):
                raise _unauthorized("Unable to verify access token") from None


bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = None,
) -> AuthenticatedUser:
    if credentials is None:
        credentials = await bearer(request)
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized("Authentication required")
    verifier: SupabaseJwtVerifier = request.app.state.auth_verifier
    return await verifier.verify(credentials.credentials)


async def require_permanent_user(request: Request) -> AuthenticatedUser:
    user = await get_current_user(request)
    if user.is_anonymous:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A permanent account is required",
        )
    return user


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )
