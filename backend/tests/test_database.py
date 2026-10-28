from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import UniqueConstraint
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings
from app.database import get_db_session, normalize_database_url
from app.main import create_app
from app.models import (
    ActualGenerationRecordModel,
    ForecastPublicationRecordModel,
    SavedAnalysisConfiguration,
)
from app.services.generation import GenerationService
from app.services.persistence import PersistenceService
from app.services.source_status import SourceStatusRegistry


class StubElexonClient:
    def __init__(self):
        self.actual_data = []
        self.forecast_data = []

    async def fetch_actuals(self, _start, _end):
        return self.actual_data

    async def fetch_forecasts(self, _start, _end):
        return self.forecast_data


def test_database_url_is_secret_and_driver_is_normalized():
    settings = Settings(app_env="test", database_url="postgresql://user:secret@host/db")
    assert "secret" not in repr(settings.database_url)
    assert normalize_database_url(settings.database_url.get_secret_value()).startswith(
        "postgresql+psycopg://"
    )
    normalized = normalize_database_url(
        "postgresql://user:p#ss@db.example/test?pgbouncer=true&sslmode=require"
    )
    assert "p#ss" not in normalized
    assert "p%23ss" in normalized
    assert "pgbouncer" not in normalized
    assert "sslmode=require" in normalized


def test_database_constraints_and_query_indexes_exist():
    actual_constraints = {
        item.name
        for item in ActualGenerationRecordModel.__table__.constraints
        if isinstance(item, UniqueConstraint)
    }
    forecast_constraints = {
        item.name
        for item in ForecastPublicationRecordModel.__table__.constraints
        if isinstance(item, UniqueConstraint)
    }
    saved_constraints = {
        item.name
        for item in SavedAnalysisConfiguration.__table__.constraints
        if isinstance(item, UniqueConstraint)
    }
    assert "uq_actual_source_delivery_generation" in actual_constraints
    assert "uq_forecast_source_delivery_publication_generation" in forecast_constraints
    assert "uq_saved_analysis_user_name" in saved_constraints
    assert "ix_actual_generation_delivery_time" in {
        item.name for item in ActualGenerationRecordModel.__table__.indexes
    }
    assert "ix_forecast_delivery_publication_time" in {
        item.name for item in ForecastPublicationRecordModel.__table__.indexes
    }


@pytest.mark.asyncio
async def test_database_health_is_sanitized_when_unconfigured():
    app = create_app(Settings(app_env="test", database_url=None), client=StubElexonClient())
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/health/database")
    assert response.status_code == 503
    assert response.json() == {"detail": "Database is not configured"}


@pytest.mark.asyncio
async def test_database_health_reports_connected_without_exposing_details():
    class HealthySession:
        async def execute(self, _statement):
            return None

    async def healthy_session():
        yield HealthySession()

    app = create_app(Settings(app_env="test", database_url=None), client=StubElexonClient())
    app.dependency_overrides[get_db_session] = healthy_session
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/health/database")
    assert response.status_code == 200
    assert response.json() == {"status": "connected"}


class RecordingPersistence:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.events = []

    async def start_run(self, dataset, start, end):
        self.events.append(("start", dataset, start, end))
        return None if self.fail else "run-id"

    async def complete_actuals(self, run_id, records):
        self.events.append(("actuals", run_id, len(records)))
        if self.fail:
            raise RuntimeError("simulated persistence failure")

    async def complete_forecasts(self, run_id, records):
        self.events.append(("forecasts", run_id, len(records)))

    async def fail_run(self, run_id, dataset, error_code):
        self.events.append(("failed", run_id, dataset, error_code))


@pytest.mark.asyncio
async def test_generation_records_successful_ingestion_without_changing_response():
    client = StubElexonClient()
    client.actual_data = [
        {"fuelType": "WIND", "startTime": "2025-01-01T00:00:00Z", "generation": 42}
    ]
    persistence = RecordingPersistence()
    service = GenerationService(
        client,
        SourceStatusRegistry(configured=True),
        7,
        persistence,  # type: ignore[arg-type]
    )
    response = await service.actuals(
        datetime(2025, 1, 1, tzinfo=UTC), datetime(2025, 1, 2, tzinfo=UTC)
    )
    assert response.records[0].generation == 42
    assert persistence.events[0][0:2] == ("start", "FUELHH")
    assert persistence.events[-1] == ("actuals", "run-id", 1)


@pytest.mark.asyncio
async def test_database_failure_does_not_replace_valid_live_data():
    class FailingFactory:
        def __call__(self):
            raise SQLAlchemyError("database unavailable")

    client = StubElexonClient()
    client.actual_data = [
        {"fuelType": "WIND", "startTime": "2025-01-01T00:00:00Z", "generation": 42}
    ]
    persistence = PersistenceService(FailingFactory())  # type: ignore[arg-type]
    service = GenerationService(
        client,
        SourceStatusRegistry(configured=True),
        7,
        persistence,  # type: ignore[arg-type]
    )
    response = await service.actuals(
        datetime(2025, 1, 1, tzinfo=UTC), datetime(2025, 1, 2, tzinfo=UTC)
    )
    assert response.records[0].generation == 42
