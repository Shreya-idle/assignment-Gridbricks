import os
import uuid

import httpx
import pytest

from app.core.config import Settings
from app.main import create_app
from app.services.auth import AuthenticatedUser, require_permanent_user

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL is not configured for disposable PostgreSQL integration tests",
)


class StubElexonClient:
    async def fetch_actuals(self, _start, _end):
        return []

    async def fetch_forecasts(self, _start, _end):
        return []


@pytest.mark.asyncio
async def test_postgres_saved_analysis_crud_and_owner_isolation():
    user_a = AuthenticatedUser(uuid.uuid4(), "a@example.com", False)
    user_b = AuthenticatedUser(uuid.uuid4(), "b@example.com", False)
    current = {"user": user_a}

    async def authenticated_user():
        return current["user"]

    app = create_app(
        Settings(app_env="test", database_url=TEST_DATABASE_URL),
        client=StubElexonClient(),
    )
    app.dependency_overrides[require_permanent_user] = authenticated_user
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            created = await client.post(
                "/api/v1/saved-analyses",
                json={
                    "name": f"phase-3-{uuid.uuid4()}",
                    "period_start": "2026-01-01T00:00:00Z",
                    "period_end": "2026-01-02T00:00:00Z",
                    "cutoff": "2025-12-31T12:00:00Z",
                },
            )
            assert created.status_code == 201
            analysis_id = created.json()["id"]

            current["user"] = user_b
            assert (await client.get("/api/v1/saved-analyses")).json() == []
            assert (
                await client.patch(
                    f"/api/v1/saved-analyses/{analysis_id}", json={"name": "Not owned"}
                )
            ).status_code == 404
            assert (await client.delete(f"/api/v1/saved-analyses/{analysis_id}")).status_code == 404

            current["user"] = user_a
            renamed = await client.patch(
                f"/api/v1/saved-analyses/{analysis_id}", json={"name": "Renamed by owner"}
            )
            assert renamed.status_code == 200
            assert renamed.json()["name"] == "Renamed by owner"
            assert (await client.delete(f"/api/v1/saved-analyses/{analysis_id}")).status_code == 204
            assert (await client.get("/api/v1/saved-analyses")).json() == []
