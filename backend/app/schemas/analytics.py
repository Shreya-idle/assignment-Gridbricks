from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.utils.datetime import require_aware


class AccuracyMetrics(BaseModel):
    mae: float | None
    rmse: float | None
    bias: float | None
    matched_intervals_count: int = Field(ge=0)


class QualityCounts(BaseModel):
    actual_intervals_count: int = Field(ge=0)
    forecast_intervals_count: int = Field(ge=0)
    matched_intervals_count: int = Field(ge=0)
    missing_forecast_count: int = Field(ge=0)
    no_eligible_forecast_count: int = Field(ge=0)
    missing_actual_count: int = Field(ge=0)
    invalid_record_count: int = Field(ge=0)
    duplicate_record_count: int = Field(ge=0)
    unmatched_forecast_count: int = Field(ge=0)


class IntervalComparison(BaseModel):
    start_time: datetime
    actual_generation: float
    forecast_generation: float
    forecast_publish_time: datetime
    error: float
    absolute_error: float
    squared_error: float


class AnalyticsPeriod(BaseModel):
    start: datetime
    end: datetime


class CutoffDetails(BaseModel):
    effective_time: datetime
    interpretation: str = "Inclusive publication-time cutoff, normalized to UTC"

    @field_validator("effective_time")
    @classmethod
    def validate_cutoff(cls, value: datetime) -> datetime:
        return require_aware(value, "cutoff")


class ForecastHistoryDetails(BaseModel):
    publication_from: datetime
    publication_to: datetime
    history_horizon_days: int = Field(ge=1)
    completeness: Literal["bounded"] = "bounded"


class ForecastAccuracyResponse(BaseModel):
    period: AnalyticsPeriod
    cutoff: CutoffDetails
    forecast_history: ForecastHistoryDetails
    metrics: AccuracyMetrics
    quality: QualityCounts
    comparisons: list[IntervalComparison]
    assumptions: list[str]
