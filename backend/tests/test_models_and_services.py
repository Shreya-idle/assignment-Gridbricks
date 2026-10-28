from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.core.errors import InvalidSourceRecordError
from app.schemas.generation import ActualGenerationRecord, ForecastGenerationRecord
from app.services.generation import GenerationService


def test_actual_accepts_zero_and_normalizes_timestamp():
    record = ActualGenerationRecord(start_time="2025-01-01T00:00:00+00:00", generation=0)
    assert record.generation == 0
    assert record.start_time.tzinfo == UTC


@pytest.mark.parametrize("value", ["NaN", "Infinity", "bad"])
def test_actual_rejects_invalid_generation(value):
    with pytest.raises(ValidationError):
        ActualGenerationRecord(start_time="2025-01-01T00:00:00Z", generation=value)


@pytest.mark.parametrize("value", [None, ""])
def test_actual_rejects_missing_or_null_generation(value):
    with pytest.raises(ValidationError):
        ActualGenerationRecord(start_time="2025-01-01T00:00:00Z", generation=value)


def test_finite_negative_generation_is_preserved():
    record = ActualGenerationRecord(start_time="2025-01-01T00:00:00Z", generation=-1)
    assert record.generation == -1


def test_models_reject_naive_and_missing_publish_time():
    with pytest.raises(ValidationError):
        ActualGenerationRecord(start_time=datetime(2025, 1, 1), generation=1)
    with pytest.raises(ValidationError):
        ForecastGenerationRecord(start_time="2025-01-01T00:00:00Z", generation=1)


def test_actual_filtering():
    raw = [
        {"fuelType": "CCGT", "startTime": "2025-01-01T00:00:00Z", "generation": 5},
        {"fuelType": "WIND", "startTime": "2025-01-01T00:00:00Z", "generation": 7},
    ]
    records = GenerationService._normalize_actuals(raw)
    assert len(records) == 1
    assert records[0].fuel_type == "WIND"


def test_invalid_wind_record_is_reported():
    with pytest.raises(InvalidSourceRecordError):
        GenerationService._normalize_actuals(
            [{"fuelType": "WIND", "startTime": "bad", "generation": 7}]
        )


def test_forecast_publication_versions_are_preserved():
    raw = [
        {
            "startTime": "2025-01-02T00:00:00Z",
            "publishTime": "2025-01-01T08:00:00Z",
            "generation": 5,
        },
        {
            "startTime": "2025-01-02T00:00:00Z",
            "publishTime": "2025-01-01T12:00:00Z",
            "generation": 6,
        },
    ]
    records = GenerationService._normalize_forecasts(raw)
    assert len(records) == 2
    assert records[0].publish_time != records[1].publish_time
