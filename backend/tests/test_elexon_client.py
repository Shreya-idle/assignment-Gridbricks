from datetime import UTC, datetime

import httpx
import pytest

from app.clients.elexon import ElexonClient
from app.core.errors import (
    UpstreamAuthenticationError,
    UpstreamConnectionError,
    UpstreamRateLimitError,
    UpstreamResponseError,
    UpstreamServerError,
    UpstreamTimeoutError,
)

START = datetime(2025, 1, 1, tzinfo=UTC)
END = datetime(2025, 1, 2, tzinfo=UTC)


def make_client(handler, retries=0, sleeps=None):
    async def sleep(delay):
        if sleeps is not None:
            sleeps.append(delay)

    return ElexonClient(
        "https://example.test", 1, retries, transport=httpx.MockTransport(handler), sleep=sleep
    )


@pytest.mark.asyncio
async def test_valid_actual_response_and_query_parameters():
    def handler(request):
        assert request.url.path == "/datasets/FUELHH/stream"
        assert request.url.params["publishDateTimeFrom"] == "2025-01-01T00:00:00Z"
        assert request.url.params["publishDateTimeTo"] == "2025-01-02T00:00:00Z"
        assert request.url.params["format"] == "json"
        return httpx.Response(200, json=[{"fuelType": "WIND"}])

    async with make_client(handler) as client:
        assert await client.fetch_actuals(START, END) == [{"fuelType": "WIND"}]


@pytest.mark.asyncio
async def test_forecast_uses_windfor_dataset_path():
    def handler(request):
        assert request.url.path == "/datasets/WINDFOR/stream"
        return httpx.Response(200, json=[])

    async with make_client(handler) as client:
        assert await client.fetch_forecasts(START, END) == []


@pytest.mark.asyncio
async def test_data_envelope_and_empty_success():
    async with make_client(lambda _r: httpx.Response(200, json={"data": []})) as client:
        assert await client.fetch_forecasts(START, END) == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="html", headers={"content-type": "text/html"}),
        httpx.Response(200, content=b"{", headers={"content-type": "application/json"}),
        httpx.Response(200, json={"unexpected": []}),
    ],
)
async def test_invalid_responses(response):
    async with make_client(lambda _r: response) as client:
        with pytest.raises(UpstreamResponseError):
            await client.fetch_actuals(START, END)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,error",
    [(401, UpstreamAuthenticationError), (403, UpstreamAuthenticationError)],
)
async def test_auth_errors(status, error):
    async with make_client(lambda _r: httpx.Response(status)) as client:
        with pytest.raises(error):
            await client.fetch_actuals(START, END)


@pytest.mark.asyncio
async def test_rate_limit_honors_retry_after_and_exhausts():
    sleeps = []
    async with make_client(
        lambda _r: httpx.Response(429, headers={"retry-after": "2"}), retries=1, sleeps=sleeps
    ) as client:
        with pytest.raises(UpstreamRateLimitError):
            await client.fetch_actuals(START, END)
    assert sleeps == [2.0]


@pytest.mark.asyncio
async def test_server_retry_then_success():
    count = 0

    def handler(_request):
        nonlocal count
        count += 1
        return httpx.Response(503) if count == 1 else httpx.Response(200, json=[])

    async with make_client(handler, retries=1) as client:
        assert await client.fetch_actuals(START, END) == []
    assert count == 2


@pytest.mark.asyncio
async def test_server_retry_exhaustion():
    async with make_client(lambda _r: httpx.Response(500), retries=1) as client:
        with pytest.raises(UpstreamServerError):
            await client.fetch_actuals(START, END)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exc,error",
    [
        (httpx.ReadTimeout("timeout"), UpstreamTimeoutError),
        (httpx.ConnectError("connection"), UpstreamConnectionError),
    ],
)
async def test_transport_errors(exc, error):
    def handler(request):
        exc.request = request
        raise exc

    async with make_client(handler) as client:
        with pytest.raises(error):
            await client.fetch_actuals(START, END)
