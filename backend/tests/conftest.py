from collections.abc import AsyncIterator

import httpx
import pytest

from app.core.config import Settings
from app.main import create_app


class StubElexonClient:
    def __init__(self) -> None:
        self.actual_data: list[dict] = []
        self.forecast_data: list[dict] = []
        self.error: Exception | None = None
        self.actual_calls: list[tuple] = []
        self.forecast_calls: list[tuple] = []

    async def fetch_actuals(self, start, end):
        self.actual_calls.append((start, end))
        if self.error:
            raise self.error
        return self.actual_data

    async def fetch_forecasts(self, start, end):
        self.forecast_calls.append((start, end))
        if self.error:
            raise self.error
        return self.forecast_data


@pytest.fixture
def stub() -> StubElexonClient:
    return StubElexonClient()


@pytest.fixture
async def api_client(stub: StubElexonClient) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(Settings(app_env="test", database_url=None), client=stub)  # type: ignore[arg-type]
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client
