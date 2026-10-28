import math
from datetime import UTC, datetime, timedelta

import pytest

from app.core.errors import UpstreamServerError
from app.schemas.analytics import IntervalComparison
from app.schemas.generation import ActualGenerationRecord, ForecastGenerationRecord
from app.services.analytics import (
    AnalyticsService,
    analyze_records,
    calculate_metrics,
    match_intervals,
    select_forecasts,
)
from app.services.generation import GenerationService
from app.services.source_status import SourceStatusRegistry


def actual(at: str, generation: float) -> ActualGenerationRecord:
    return ActualGenerationRecord(start_time=at, generation=generation)


def forecast(at: str, published: str, generation: float) -> ForecastGenerationRecord:
    return ForecastGenerationRecord(start_time=at, publish_time=published, generation=generation)


def comparison(error: float) -> IntervalComparison:
    return IntervalComparison(
        start_time="2025-01-01T00:00:00Z",
        actual_generation=0,
        forecast_generation=error,
        forecast_publish_time="2024-12-31T00:00:00Z",
        error=error,
        absolute_error=abs(error),
        squared_error=error * error,
    )


def test_cutoff_selects_latest_inclusive_and_excludes_future():
    records = [
        forecast("2025-01-02T00:00:00Z", "2025-01-01T08:00:00Z", 10),
        forecast("2025-01-02T00:00:00Z", "2025-01-01T10:00:00Z", 20),
        forecast("2025-01-02T00:00:00Z", "2025-01-01T10:00:00.001Z", 30),
    ]
    result = select_forecasts(records, datetime(2025, 1, 1, 10, tzinfo=UTC))
    assert result.selected[datetime(2025, 1, 2, tzinfo=UTC)].generation == 20


def test_cutoff_normalizes_timezones_and_has_order_independent_duplicate_tie_break():
    records = [
        forecast("2025-01-02T01:00:00+01:00", "2025-01-01T11:00:00+01:00", 10),
        forecast("2025-01-02T00:00:00Z", "2025-01-01T10:00:00Z", 12),
    ]
    first = select_forecasts(records, datetime(2025, 1, 1, 10, tzinfo=UTC))
    second = select_forecasts(list(reversed(records)), datetime(2025, 1, 1, 10, tzinfo=UTC))
    assert next(iter(first.selected.values())).generation == 12
    assert first.selected == second.selected
    assert first.duplicate_count == 1


def test_all_forecasts_after_cutoff_and_empty_input():
    records = [forecast("2025-01-02T00:00:00Z", "2025-01-01T10:00:01Z", 10)]
    result = select_forecasts(records, datetime(2025, 1, 1, 10, tzinfo=UTC))
    assert result.selected == {}
    assert result.all_intervals
    assert select_forecasts([], datetime(2025, 1, 1, tzinfo=UTC)).selected == {}


def test_matching_uses_timestamp_not_input_order_and_accepts_zero():
    actuals = [actual("2025-01-01T00:30:00Z", 5), actual("2025-01-01T00:00:00Z", 0)]
    selected = {
        item.start_time: item
        for item in [
            forecast("2025-01-01T01:30:00+01:00", "2024-12-31T00:00:00Z", 0),
            forecast("2025-01-01T00:00:00Z", "2024-12-31T00:00:00Z", 2),
        ]
    }
    result = match_intervals(actuals, selected)
    assert [item.error for item in result.comparisons] == [2, -5]
    assert result.missing_actual_count == 0


def test_duplicate_actual_is_counted_and_canonical():
    interval = "2025-01-01T00:00:00Z"
    selected_record = forecast(interval, "2024-12-31T00:00:00Z", 10)
    result = match_intervals(
        [actual(interval, 8), actual(interval, 6)], {selected_record.start_time: selected_record}
    )
    assert result.duplicate_actual_count == 1
    assert result.comparisons[0].actual_generation == 6


def test_metrics_hand_calculated_and_empty():
    metrics = calculate_metrics([comparison(10), comparison(-20), comparison(30)])
    assert metrics.mae == pytest.approx(20)
    assert metrics.rmse == pytest.approx(math.sqrt(1400 / 3))
    assert metrics.bias == pytest.approx(20 / 3)
    assert metrics.matched_intervals_count == 3
    empty = calculate_metrics([])
    assert (empty.mae, empty.rmse, empty.bias) == (None, None, None)


def test_quality_distinguishes_missing_late_unmatched_and_duplicates():
    start = datetime(2025, 1, 1, tzinfo=UTC)
    end = datetime(2025, 1, 2, tzinfo=UTC)
    actuals = [
        actual("2025-01-01T00:00:00Z", 1),
        actual("2025-01-01T00:30:00Z", 2),
        actual("2025-01-01T01:00:00Z", 3),
        actual("2025-01-01T01:00:00Z", 4),
    ]
    forecasts = [
        forecast("2025-01-01T00:30:00Z", "2025-01-01T10:01:00Z", 2),
        forecast("2025-01-01T01:00:00Z", "2025-01-01T09:00:00Z", 3),
        forecast("2025-01-01T02:00:00Z", "2025-01-01T09:00:00Z", 5),
    ]
    cutoff = datetime(2025, 1, 1, 10, tzinfo=UTC)
    response = analyze_records(
        actuals,
        forecasts,
        start,
        end,
        cutoff,
        cutoff - timedelta(days=7),
        7,
    )
    assert response.quality.actual_intervals_count == 3
    assert response.quality.forecast_intervals_count == 3
    assert response.quality.missing_forecast_count == 1
    assert response.quality.no_eligible_forecast_count == 1
    assert response.quality.unmatched_forecast_count == 1
    assert response.quality.missing_actual_count == 1
    assert response.quality.duplicate_record_count == 1
    assert response.metrics.matched_intervals_count == 1


@pytest.mark.asyncio
async def test_analytics_service_retrieves_bounded_publication_history_and_selects_cutoff():
    class WindowedElexonClient:
        def __init__(self):
            self.forecast_calls = []

        async def fetch_actuals(self, _start, _end):
            return [
                {"fuelType": "WIND", "startTime": "2025-01-02T00:00:00Z", "generation": 100},
                {"fuelType": "WIND", "startTime": "2025-01-02T00:30:00Z", "generation": 200},
            ]

        async def fetch_forecasts(self, start, end):
            self.forecast_calls.append((start, end))
            records = [
                {
                    "startTime": "2025-01-02T00:30:00Z",
                    "publishTime": "2024-12-25T09:00:00Z",
                    "generation": 190,
                },
                {
                    "startTime": "2025-01-02T00:00:00Z",
                    "publishTime": "2024-12-31T08:00:00Z",
                    "generation": 110,
                },
                {
                    "startTime": "2025-01-02T00:00:00Z",
                    "publishTime": "2025-01-01T10:00:00Z",
                    "generation": 120,
                },
                {
                    "startTime": "2025-01-02T00:00:00Z",
                    "publishTime": "2025-01-01T10:00:00.500Z",
                    "generation": 999,
                },
            ]
            return [
                item
                for item in records
                if start <= datetime.fromisoformat(item["publishTime"].replace("Z", "+00:00")) < end
            ]

    client = WindowedElexonClient()
    generation = GenerationService(client, SourceStatusRegistry(configured=True), 7)  # type: ignore[arg-type]
    service = AnalyticsService(generation, max_range_days=7, forecast_history_days=7)
    cutoff = datetime(2025, 1, 1, 10, tzinfo=UTC)

    response = await service.forecast_accuracy(
        datetime(2025, 1, 2, tzinfo=UTC),
        datetime(2025, 1, 2, 1, 0, tzinfo=UTC),
        cutoff,
    )

    assert client.forecast_calls == [
        (
            datetime(2024, 12, 25, 10, 0, 1, tzinfo=UTC),
            datetime(2025, 1, 1, 10, 0, 1, tzinfo=UTC),
        )
    ]
    assert response.metrics.mae == 20
    assert response.comparisons[0].forecast_generation == 120
    assert response.comparisons[0].forecast_publish_time == cutoff
    assert response.quality.missing_forecast_count == 1
    assert response.forecast_history.completeness == "bounded"
    assert response.forecast_history.publication_from == datetime(
        2024, 12, 25, 10, 0, 1, tzinfo=UTC
    )
    assert set(response.model_dump()["forecast_history"]) == {
        "publication_from",
        "publication_to",
        "history_horizon_days",
        "completeness",
    }


@pytest.mark.asyncio
async def test_analytics_service_propagates_forecast_history_upstream_failure():
    class FailingForecastClient:
        async def fetch_actuals(self, _start, _end):
            return []

        async def fetch_forecasts(self, _start, _end):
            raise UpstreamServerError("Elexon unavailable")

    generation = GenerationService(
        FailingForecastClient(),  # type: ignore[arg-type]
        SourceStatusRegistry(configured=True),
        7,
    )
    service = AnalyticsService(generation, max_range_days=7, forecast_history_days=7)

    with pytest.raises(UpstreamServerError):
        await service.forecast_accuracy(
            datetime(2025, 1, 2, tzinfo=UTC),
            datetime(2025, 1, 2, 1, tzinfo=UTC),
            datetime(2025, 1, 1, 10, tzinfo=UTC),
        )


@pytest.mark.asyncio
async def test_analytics_endpoint_success_empty_and_naive_cutoff(api_client, stub):
    stub.actual_data = [
        {"fuelType": "WIND", "startTime": "2025-01-01T00:00:00Z", "generation": 100}
    ]
    stub.forecast_data = [
        {
            "startTime": "2025-01-01T00:00:00Z",
            "publishTime": "2024-12-31T12:00:00Z",
            "generation": 110,
        }
    ]
    params = {
        "from": "2025-01-01T00:00:00Z",
        "to": "2025-01-02T00:00:00Z",
        "cutoff": "2025-01-01T00:00:00Z",
    }
    response = await api_client.get("/api/v1/analytics/forecast-accuracy", params=params)
    assert response.status_code == 200
    assert response.json()["metrics"]["mae"] == 10
    assert response.json()["forecast_history"]["completeness"] == "bounded"
    assert set(response.json()["forecast_history"]) == {
        "publication_from",
        "publication_to",
        "history_horizon_days",
        "completeness",
    }
    stub.actual_data = []
    stub.forecast_data = []
    empty = await api_client.get("/api/v1/analytics/forecast-accuracy", params=params)
    assert empty.json()["metrics"]["mae"] is None
    params["cutoff"] = "2025-01-01T00:00:00"
    invalid = await api_client.get("/api/v1/analytics/forecast-accuracy", params=params)
    assert invalid.status_code == 422


@pytest.mark.asyncio
async def test_analytics_endpoint_propagates_malformed_upstream(api_client, stub):
    stub.actual_data = [{"fuelType": "WIND", "startTime": "bad", "generation": 1}]
    response = await api_client.get(
        "/api/v1/analytics/forecast-accuracy",
        params={
            "from": "2025-01-01T00:00:00Z",
            "to": "2025-01-02T00:00:00Z",
            "cutoff": "2025-01-01T00:00:00Z",
        },
    )
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "invalid_source_record"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "params",
    [
        {
            "from": "2025-01-01T00:00:00Z",
            "to": "2025-01-01T00:00:00Z",
            "cutoff": "2024-12-31T12:00:00Z",
        },
        {
            "from": "2025-01-02T00:00:00Z",
            "to": "2025-01-01T00:00:00Z",
            "cutoff": "2024-12-31T12:00:00Z",
        },
        {
            "from": "2025-01-01T00:00:00Z",
            "to": "2025-01-09T00:00:00Z",
            "cutoff": "2024-12-31T12:00:00Z",
        },
    ],
)
async def test_analytics_endpoint_rejects_invalid_delivery_ranges(api_client, params):
    response = await api_client.get("/api/v1/analytics/forecast-accuracy", params=params)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_date_range"


def test_delivery_boundaries_are_start_inclusive_end_exclusive_across_dst_offsets():
    response = analyze_records(
        actuals=[
            actual("2025-03-30T00:00:00Z", 10),
            actual("2025-03-30T02:00:00+01:00", 20),
        ],
        forecasts=[
            forecast("2025-03-30T00:00:00Z", "2025-03-29T12:00:00Z", 12),
            forecast("2025-03-30T02:00:00+01:00", "2025-03-29T12:00:00Z", 22),
        ],
        start=datetime.fromisoformat("2025-03-30T00:00:00+00:00"),
        end=datetime.fromisoformat("2025-03-30T02:00:00+01:00"),
        cutoff=datetime.fromisoformat("2025-03-29T12:00:00+00:00"),
        history_start=datetime.fromisoformat("2025-03-22T12:00:00+00:00"),
        history_horizon_days=7,
    )
    assert response.metrics.matched_intervals_count == 1
    assert response.comparisons[0].start_time == datetime(2025, 3, 30, tzinfo=UTC)


def test_autumn_dst_repeated_hour_matches_by_absolute_utc_time():
    response = analyze_records(
        actuals=[
            actual("2025-10-26T01:30:00+01:00", 100),
            actual("2025-10-26T01:30:00+00:00", 200),
        ],
        forecasts=[
            forecast("2025-10-26T00:30:00Z", "2025-10-25T12:00:00Z", 110),
            forecast("2025-10-26T01:30:00Z", "2025-10-25T12:00:00Z", 190),
        ],
        start=datetime.fromisoformat("2025-10-26T01:00:00+01:00"),
        end=datetime.fromisoformat("2025-10-26T02:00:00+00:00"),
        cutoff=datetime.fromisoformat("2025-10-25T12:00:00Z"),
        history_start=datetime.fromisoformat("2025-10-18T12:00:00Z"),
        history_horizon_days=7,
    )
    assert response.metrics.matched_intervals_count == 2
    assert [item.error for item in response.comparisons] == [10, -10]
    assert response.metrics.mae == 10
    assert response.metrics.rmse == 10
    assert response.metrics.bias == 0


def test_cutoff_equivalent_offsets_are_inclusive_at_dst_boundary():
    record = forecast(
        "2025-03-30T02:00:00+01:00",
        "2025-03-30T01:00:00Z",
        42,
    )
    selected = select_forecasts([record], datetime.fromisoformat("2025-03-30T02:00:00+01:00"))
    assert selected.selected[datetime(2025, 3, 30, 1, tzinfo=UTC)].generation == 42


def test_unmatched_only_data_has_null_metrics_and_quality_counts():
    response = analyze_records(
        actuals=[actual("2025-01-01T00:00:00Z", 10)],
        forecasts=[forecast("2025-01-01T00:30:00Z", "2024-12-31T12:00:00Z", 20)],
        start=datetime(2025, 1, 1, tzinfo=UTC),
        end=datetime(2025, 1, 1, 1, tzinfo=UTC),
        cutoff=datetime(2024, 12, 31, 12, tzinfo=UTC),
        history_start=datetime(2024, 12, 24, 12, tzinfo=UTC),
        history_horizon_days=7,
    )
    assert response.metrics.mae is None
    assert response.metrics.rmse is None
    assert response.metrics.bias is None
    assert response.quality.missing_forecast_count == 1
    assert response.quality.missing_actual_count == 1
