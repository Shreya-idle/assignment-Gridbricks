import uuid
from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.config import Settings
from app.database import get_db_session
from app.main import create_app
from app.services.auth import AuthenticatedUser


class StubElexonClient:
    async def fetch_actuals(self, _start, _end):
        return []

    async def fetch_forecasts(self, _start, _end):
        return []


class RejectingVerifier:
    def __init__(self, anonymous: bool = False, user_id: uuid.UUID | None = None):
        self.anonymous = anonymous
        self.user_id = user_id or uuid.uuid4()

    async def verify(self, _token: str) -> AuthenticatedUser:
        return AuthenticatedUser(self.user_id, None, self.anonymous)

    async def aclose(self):
        return None


async def empty_session() -> AsyncIterator[object]:
    yield object()


async def _request(anonymous: bool, headers: dict[str, str] | None = None):
    app = create_app(Settings(app_env="test", database_url=None), client=StubElexonClient())
    app.dependency_overrides[get_db_session] = empty_session
    async with app.router.lifespan_context(app):
        app.state.auth_verifier = RejectingVerifier(anonymous)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.get("/api/v1/saved-analyses", headers=headers)


@pytest.mark.asyncio
async def test_saved_analyses_require_a_bearer_token():
    response = await _request(False)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_anonymous_guests_cannot_access_saved_analyses():
    response = await _request(True, {"Authorization": "Bearer guest-token"})
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_saved_analysis_payload_rejects_naive_and_long_ranges():
    from app.schemas.saved_analyses import SavedAnalysisCreate

    with pytest.raises(ValueError):
        SavedAnalysisCreate(
            name="test",
            period_start="2026-01-01T00:00:00",
            period_end="2026-01-02T00:00:00Z",
            cutoff="2025-12-31T12:00:00Z",
        )
    with pytest.raises(ValueError):
        SavedAnalysisCreate(
            name="test",
            period_start="2026-01-01T00:00:00Z",
            period_end="2026-01-08T00:00:01Z",
            cutoff="2025-12-31T12:00:00Z",
        )


@pytest.mark.asyncio
async def test_other_users_records_are_not_listed_or_mutated():
    user_id = uuid.uuid4()

    class Result:
        rowcount = 0

    class RecordingSession:
        def __init__(self):
            self.statements = []

        async def scalars(self, statement):
            self.statements.append(statement)
            return []

        async def execute(self, statement):
            self.statements.append(statement)
            return Result()

        async def scalar(self, statement):
            self.statements.append(statement)
            return None

        async def commit(self):
            return None

        async def rollback(self):
            return None

    session = RecordingSession()

    async def recording_session():
        yield session

    app = create_app(Settings(app_env="test", database_url=None), client=StubElexonClient())
    app.dependency_overrides[get_db_session] = recording_session
    async with app.router.lifespan_context(app):
        app.state.auth_verifier = RejectingVerifier(False, user_id)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            headers = {"Authorization": "Bearer valid-token"}
            listed = await client.get("/api/v1/saved-analyses", headers=headers)
            renamed = await client.patch(
                f"/api/v1/saved-analyses/{uuid.uuid4()}",
                headers=headers,
                json={"name": "Cannot rename another user's record"},
            )
            deleted = await client.delete(f"/api/v1/saved-analyses/{uuid.uuid4()}", headers=headers)
    assert listed.json() == []
    assert renamed.status_code == 404
    assert deleted.status_code == 404
    assert session.statements
    assert all(
        str(user_id) in str(statement.compile().params.values()) for statement in session.statements
    )


@pytest.mark.asyncio
async def test_saved_analysis_database_errors_are_sanitized():
    class FailingSession:
        async def scalars(self, _statement):
            raise SQLAlchemyError("database host and credentials must not leak")

        def add(self, _item):
            return None

        async def commit(self):
            raise SQLAlchemyError("database host and credentials must not leak")

        async def rollback(self):
            return None

    async def failing_session():
        yield FailingSession()

    app = create_app(Settings(app_env="test", database_url=None), client=StubElexonClient())
    app.dependency_overrides[get_db_session] = failing_session
    async with app.router.lifespan_context(app):
        app.state.auth_verifier = RejectingVerifier(False)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            headers = {"Authorization": "Bearer valid-token"}
            listed = await client.get("/api/v1/saved-analyses", headers=headers)
            created = await client.post(
                "/api/v1/saved-analyses",
                headers=headers,
                json={
                    "name": "Database failure",
                    "period_start": "2026-01-01T00:00:00Z",
                    "period_end": "2026-01-02T00:00:00Z",
                    "cutoff": "2025-12-31T12:00:00Z",
                },
            )
    assert listed.status_code == 503
    assert created.status_code == 503
    assert listed.json() == {"detail": "Saved analyses are temporarily unavailable"}
    assert "credentials" not in created.text


@pytest.mark.asyncio
async def test_duplicate_saved_analysis_name_returns_conflict():
    class DuplicateSession:
        def add(self, _item):
            return None

        async def commit(self):
            raise IntegrityError("insert", {}, Exception("duplicate"))

        async def rollback(self):
            return None

    async def duplicate_session():
        yield DuplicateSession()

    app = create_app(Settings(app_env="test", database_url=None), client=StubElexonClient())
    app.dependency_overrides[get_db_session] = duplicate_session
    async with app.router.lifespan_context(app):
        app.state.auth_verifier = RejectingVerifier(False)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/saved-analyses",
                headers={"Authorization": "Bearer valid-token"},
                json={
                    "name": "Duplicate",
                    "period_start": "2026-01-01T00:00:00Z",
                    "period_end": "2026-01-02T00:00:00Z",
                    "cutoff": "2025-12-31T12:00:00Z",
                },
            )
    assert response.status_code == 409
