from collections.abc import AsyncIterator
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import Settings


def normalize_database_url(url: str) -> str:
    """Select Psycopg's async SQLAlchemy driver without altering credentials."""
    if url.startswith("postgresql+psycopg://"):
        normalized = url
    elif url.startswith("postgresql://"):
        normalized = url.replace("postgresql://", "postgresql+psycopg://", 1)
    elif url.startswith("postgres://"):
        normalized = url.replace("postgres://", "postgresql+psycopg://", 1)
    else:
        return url
    prefix, remainder = normalized.split("://", 1)
    if "@" not in remainder or ":" not in remainder.rsplit("@", 1)[0]:
        return normalized
    userinfo, location = remainder.rsplit("@", 1)
    username, password = userinfo.split(":", 1)
    safe_userinfo = f"{quote(username, safe='%')}:{quote(password, safe='%')}"
    normalized = f"{prefix}://{safe_userinfo}@{location}"
    parts = urlsplit(normalized)
    unsupported_options = {"connection_limit", "pgbouncer", "pool_timeout"}
    query = urlencode(
        [(key, value) for key, value in parse_qsl(parts.query) if key not in unsupported_options]
    )
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))


def create_database_resources(
    settings: Settings,
) -> tuple[AsyncEngine | None, async_sessionmaker[AsyncSession] | None]:
    if settings.database_url is None:
        return None, None
    async_url = normalize_database_url(settings.database_url.get_secret_value()).replace(
        "postgresql+psycopg://", "postgresql+asyncpg://", 1
    )
    engine = create_async_engine(
        async_url,
        echo=False,
        pool_pre_ping=True,
        poolclass=NullPool,
        connect_args={"prepared_statement_cache_size": 0, "statement_cache_size": 0},
    )
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    factory: async_sessionmaker[AsyncSession] | None = getattr(
        request.app.state, "db_session_factory", None
    )
    if factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not configured",
        )
    async with factory() as session:
        yield session
