import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_defaults_and_cors_parsing():
    settings = Settings(cors_origins=["http://localhost:5173", "https://example.com"])
    assert settings.app_name == "WindSight API"
    assert settings.cors_origins == ["http://localhost:5173", "https://example.com"]


def test_supabase_settings_derive_issuer_without_exposing_key():
    settings = Settings(
        app_env="test",
        database_url=None,
        supabase_url="https://project.supabase.co/",
        supabase_publishable_key="publishable-secret-value",
    )
    assert settings.supabase_jwt_issuer == "https://project.supabase.co/auth/v1"
    assert "publishable-secret-value" not in repr(settings.supabase_publishable_key)


def test_cors_origins_json_environment_override(monkeypatch):
    monkeypatch.setenv(
        "CORS_ORIGINS",
        '["http://localhost:5173","http://127.0.0.1:5173"]',
    )

    settings = Settings()

    assert settings.cors_origins == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


@pytest.mark.parametrize("field,value", [("elexon_timeout_seconds", 0), ("elexon_max_retries", 6)])
def test_invalid_numeric_settings(field, value):
    with pytest.raises(ValidationError):
        Settings(**{field: value})


def test_environment_override(monkeypatch):
    monkeypatch.setenv("APP_NAME", "Configured")
    assert Settings().app_name == "Configured"


def test_analytics_history_cannot_exceed_upstream_range():
    with pytest.raises(ValidationError):
        Settings(elexon_max_range_days=7, analytics_forecast_history_days=8)
