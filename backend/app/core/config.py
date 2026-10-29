from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, HttpUrl, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "WindSight API"
    app_env: Literal["development", "test", "staging", "production"] = "development"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"
    elexon_base_url: HttpUrl = HttpUrl("https://data.elexon.co.uk/bmrs/api/v1")
    elexon_timeout_seconds: float = Field(default=30, gt=0, le=120)
    elexon_max_retries: int = Field(default=3, ge=0, le=5)
    elexon_max_range_days: int = Field(default=7, ge=1, le=31)
    analytics_forecast_history_days: int = Field(default=7, ge=1, le=31)
    cors_origins: list[str] = ["https://assignmentgridbricks.vercel.app"]
    default_timezone: str = "Europe/London"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    database_url: SecretStr | None = None
    supabase_url: HttpUrl | None = None
    supabase_publishable_key: SecretStr | None = None
    supabase_jwt_audience: str = "authenticated"
    supabase_jwks_cache_seconds: int = Field(default=600, ge=60, le=600)

    @property
    def supabase_jwt_issuer(self) -> str | None:
        if self.supabase_url is None:
            return None
        return f"{str(self.supabase_url).rstrip('/')}/auth/v1"

    @model_validator(mode="after")
    def validate_analytics_history_range(self) -> Self:
        if self.analytics_forecast_history_days > self.elexon_max_range_days:
            raise ValueError("analytics_forecast_history_days cannot exceed elexon_max_range_days")
        return self

    @model_validator(mode="after")
    def select_sqlalchemy_database_url(self) -> Self:
        """Ignore a legacy Prisma URL when the root env also has a PostgreSQL URL."""
        if self.database_url is None:
            return self
        value = self.database_url.get_secret_value()
        if not value.startswith("prisma+postgres://"):
            return self
        supported = _first_postgresql_url(PROJECT_ROOT / ".env")
        if supported is None:
            raise ValueError(
                "DATABASE_URL must use postgresql://, postgres://, or postgresql+psycopg://"
            )
        self.database_url = SecretStr(supported)
        return self


def _first_postgresql_url(path: Path) -> str | None:
    """Read only the first SQLAlchemy-compatible DATABASE_URL without logging it."""
    if not path.is_file():
        return None
    supported_prefixes = ("postgresql://", "postgres://", "postgresql+psycopg://")
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.lstrip().startswith("DATABASE_URL="):
            continue
        value = line.split("=", 1)[1].strip().strip('"').strip("'")
        if value.startswith(supported_prefixes):
            return value
    return None


@lru_cache
def get_settings() -> Settings:
    return Settings()
