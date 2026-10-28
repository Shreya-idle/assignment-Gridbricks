import httpx
import pytest

from app.core.errors import (
    UpstreamRateLimitError,
    UpstreamResponseError,
    UpstreamServerError,
    UpstreamTimeoutError,
)


@pytest.mark.asyncio
async def test_health_and_sources_start_not_checked(api_client: httpx.AsyncClient):
    health = await api_client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    sources = await api_client.get("/api/v1/data-sources")
    assert sources.status_code == 200
    assert {item["last_retrieval_status"] for item in sources.json()} == {"not_checked"}
    assert {item["dataset"] for item in sources.json()} == {"FUELHH", "WINDFOR"}
    assert all("documentation_url" in item for item in sources.json())
    assert all("api_key" not in item for item in sources.json())


@pytest.mark.asyncio
async def test_data_sources_repeated_requests_are_stable(api_client: httpx.AsyncClient):
    first = await api_client.get("/api/v1/data-sources")
    second = await api_client.get("/api/v1/data-sources")
    assert first.json() == second.json()


@pytest.mark.asyncio
async def test_data_sources_reflect_success_without_exposing_records(api_client, stub):
    stub.actual_data = [{"fuelType": "WIND", "startTime": "2025-01-01T00:00:00Z", "generation": 42}]
    retrieval = await api_client.get(
        "/api/v1/generation/actuals",
        params={"from": "2025-01-01T00:00:00Z", "to": "2025-01-02T00:00:00Z"},
    )
    assert retrieval.status_code == 200

    response = await api_client.get("/api/v1/data-sources")
    fuelhh = next(item for item in response.json() if item["dataset"] == "FUELHH")
    assert fuelhh["last_retrieval_status"] == "healthy"
    assert fuelhh["last_record_count"] == 1
    assert fuelhh["last_successful_retrieval"] is not None
    assert "records" not in fuelhh


@pytest.mark.asyncio
async def test_actual_endpoint(api_client, stub):
    stub.actual_data = [{"fuelType": "WIND", "startTime": "2025-01-01T00:00:00Z", "generation": 42}]
    response = await api_client.get(
        "/api/v1/generation/actuals",
        params={"from": "2025-01-01T00:00:00Z", "to": "2025-01-02T00:00:00Z"},
    )
    body = response.json()
    assert response.status_code == 200
    assert body["record_count"] == 1
    assert body["records"][0]["start_time"].endswith("Z")


@pytest.mark.asyncio
async def test_actual_endpoint_filters_delivery_boundaries_and_preserves_duplicates(
    api_client, stub
):
    stub.actual_data = [
        {"fuelType": "WIND", "startTime": "2024-12-31T23:30:00Z", "generation": 1},
        {"fuelType": "WIND", "startTime": "2025-01-01T00:00:00Z", "generation": 2},
        {"fuelType": "WIND", "startTime": "2025-01-01T00:00:00Z", "generation": 3},
        {"fuelType": "WIND", "startTime": "2025-01-01T01:00:00Z", "generation": 4},
    ]
    response = await api_client.get(
        "/api/v1/generation/actuals",
        params={"from": "2025-01-01T00:00:00Z", "to": "2025-01-01T01:00:00Z"},
    )
    assert response.status_code == 200
    assert [item["generation"] for item in response.json()["records"]] == [2, 3]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "params",
    [
        {"from": "2025-01-01T00:00:00Z", "to": "2025-01-01T00:00:00Z"},
        {"from": "2025-01-02T00:00:00Z", "to": "2025-01-01T00:00:00Z"},
        {"from": "2025-01-01T00:00:00", "to": "2025-01-02T00:00:00Z"},
        {"from": "2025-01-01T00:00:00Z", "to": "2025-01-09T00:00:00Z"},
    ],
)
async def test_actual_endpoint_rejects_invalid_ranges(api_client, params):
    response = await api_client.get("/api/v1/generation/actuals", params=params)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_forecast_empty_success(api_client, stub):
    stub.forecast_data = []
    response = await api_client.get(
        "/api/v1/generation/forecasts",
        params={"from": "2025-01-01T00:00:00Z", "to": "2025-01-02T00:00:00Z"},
    )
    assert response.status_code == 200
    assert response.json()["records"] == []


@pytest.mark.asyncio
async def test_forecast_endpoint_preserves_publication_versions(api_client, stub):
    stub.forecast_data = [
        {
            "startTime": "2025-01-02T00:00:00Z",
            "publishTime": "2025-01-01T00:00:00Z",
            "generation": 2,
        },
        {
            "startTime": "2025-01-02T00:00:00Z",
            "publishTime": "2025-01-01T00:30:00Z",
            "generation": 3,
        },
    ]
    response = await api_client.get(
        "/api/v1/generation/forecasts",
        params={"from": "2025-01-01T00:00:00Z", "to": "2025-01-01T01:00:00Z"},
    )
    assert response.status_code == 200
    assert [item["generation"] for item in response.json()["records"]] == [2, 3]
    assert response.json()["records"][0]["publish_time"].endswith("Z")


@pytest.mark.asyncio
async def test_invalid_ranges(api_client):
    response = await api_client.get(
        "/api/v1/generation/actuals",
        params={"from": "2025-01-02T00:00:00Z", "to": "2025-01-01T00:00:00Z"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_date_range"


@pytest.mark.asyncio
async def test_upstream_failure_is_not_empty_success(api_client, stub):
    stub.error = UpstreamServerError("unavailable")
    response = await api_client.get(
        "/api/v1/generation/forecasts",
        params={"from": "2025-01-01T00:00:00Z", "to": "2025-01-02T00:00:00Z"},
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "upstream_unavailable"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error,status,code",
    [
        (UpstreamTimeoutError("private detail"), 504, "upstream_timeout"),
        (UpstreamRateLimitError("private detail"), 503, "upstream_rate_limited"),
        (UpstreamResponseError("private detail"), 502, "invalid_upstream_response"),
    ],
)
async def test_generation_routes_map_known_upstream_errors(api_client, stub, error, status, code):
    stub.error = error
    response = await api_client.get(
        "/api/v1/generation/actuals",
        params={"from": "2025-01-01T00:00:00Z", "to": "2025-01-02T00:00:00Z"},
    )
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert set(response.json()["error"]) == {"code", "message"}


@pytest.mark.asyncio
async def test_cors(api_client):
    response = await api_client.options(
        "/api/v1/health",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
