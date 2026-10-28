import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.core.errors import InvalidDateRangeError
from app.schemas.analytics import (
    AccuracyMetrics,
    AnalyticsPeriod,
    CutoffDetails,
    ForecastAccuracyResponse,
    ForecastHistoryDetails,
    IntervalComparison,
    QualityCounts,
)
from app.schemas.generation import ActualGenerationRecord, ForecastGenerationRecord
from app.services.generation import GenerationService
from app.utils.datetime import require_aware, validate_date_range


@dataclass(frozen=True)
class ForecastSelection:
    selected: dict[datetime, ForecastGenerationRecord]
    all_intervals: set[datetime]
    eligible_intervals: set[datetime]
    duplicate_count: int


def select_forecasts(
    forecasts: list[ForecastGenerationRecord], cutoff: datetime
) -> ForecastSelection:
    """Select one forecast per UTC delivery interval without look-ahead bias.

    For identical delivery and publication timestamps, the highest generation is
    selected. This domain-neutral canonical tie-break is stable across input order.
    """
    cutoff = require_aware(cutoff, "cutoff")
    grouped: dict[datetime, list[ForecastGenerationRecord]] = defaultdict(list)
    duplicate_keys: Counter[tuple[datetime, datetime]] = Counter()
    for record in forecasts:
        grouped[record.start_time].append(record)
        duplicate_keys[(record.start_time, record.publish_time)] += 1

    selected: dict[datetime, ForecastGenerationRecord] = {}
    eligible_intervals: set[datetime] = set()
    for interval, versions in grouped.items():
        eligible = [record for record in versions if record.publish_time <= cutoff]
        if eligible:
            eligible_intervals.add(interval)
            selected[interval] = max(
                eligible, key=lambda item: (item.publish_time, item.generation)
            )
    return ForecastSelection(
        selected=selected,
        all_intervals=set(grouped),
        eligible_intervals=eligible_intervals,
        duplicate_count=sum(count - 1 for count in duplicate_keys.values()),
    )


@dataclass(frozen=True)
class MatchResult:
    comparisons: list[IntervalComparison]
    actual_intervals: set[datetime]
    duplicate_actual_count: int
    missing_actual_count: int


def match_intervals(
    actuals: list[ActualGenerationRecord],
    selected: dict[datetime, ForecastGenerationRecord],
) -> MatchResult:
    """Match by UTC delivery timestamp; duplicate actuals use the lowest generation."""
    actual_groups: dict[datetime, list[ActualGenerationRecord]] = defaultdict(list)
    for record in actuals:
        actual_groups[record.start_time].append(record)
    canonical_actuals = {
        interval: min(records, key=lambda item: item.generation)
        for interval, records in actual_groups.items()
    }
    comparisons: list[IntervalComparison] = []
    for interval in sorted(canonical_actuals.keys() & selected.keys()):
        actual = canonical_actuals[interval]
        forecast = selected[interval]
        error = forecast.generation - actual.generation
        comparisons.append(
            IntervalComparison(
                start_time=interval,
                actual_generation=actual.generation,
                forecast_generation=forecast.generation,
                forecast_publish_time=forecast.publish_time,
                error=error,
                absolute_error=abs(error),
                squared_error=error * error,
            )
        )
    return MatchResult(
        comparisons=comparisons,
        actual_intervals=set(canonical_actuals),
        duplicate_actual_count=sum(len(records) - 1 for records in actual_groups.values()),
        missing_actual_count=len(selected.keys() - canonical_actuals.keys()),
    )


def calculate_metrics(comparisons: list[IntervalComparison]) -> AccuracyMetrics:
    valid = [item for item in comparisons if math.isfinite(item.error)]
    count = len(valid)
    if not count:
        return AccuracyMetrics(mae=None, rmse=None, bias=None, matched_intervals_count=0)
    return AccuracyMetrics(
        mae=math.fsum(item.absolute_error for item in valid) / count,
        rmse=math.sqrt(math.fsum(item.squared_error for item in valid) / count),
        bias=math.fsum(item.error for item in valid) / count,
        matched_intervals_count=count,
    )


def analyze_records(
    actuals: list[ActualGenerationRecord],
    forecasts: list[ForecastGenerationRecord],
    start: datetime,
    end: datetime,
    cutoff: datetime,
    history_start: datetime,
    history_horizon_days: int,
    max_range_days: int = 7,
) -> ForecastAccuracyResponse:
    start, end = validate_date_range(start, end, max_range_days)
    cutoff = require_aware(cutoff, "cutoff")
    history_start = require_aware(history_start, "history_start")
    # Retrieval APIs can return records outside delivery bounds because their source
    # endpoint is publication-filtered. Analytics is strictly delivery-period scoped.
    actuals = [item for item in actuals if start <= item.start_time < end]
    forecasts = [item for item in forecasts if start <= item.start_time < end]
    selection = select_forecasts(forecasts, cutoff)
    matched = match_intervals(actuals, selection.selected)
    metrics = calculate_metrics(matched.comparisons)
    actual_intervals = matched.actual_intervals
    missing_forecast = actual_intervals - selection.all_intervals
    no_eligible = (actual_intervals & selection.all_intervals) - selection.eligible_intervals
    unmatched_forecasts = selection.all_intervals - actual_intervals
    quality = QualityCounts(
        actual_intervals_count=len(actual_intervals),
        forecast_intervals_count=len(selection.all_intervals),
        matched_intervals_count=metrics.matched_intervals_count,
        missing_forecast_count=len(missing_forecast),
        no_eligible_forecast_count=len(no_eligible),
        missing_actual_count=matched.missing_actual_count,
        invalid_record_count=0,
        duplicate_record_count=selection.duplicate_count + matched.duplicate_actual_count,
        unmatched_forecast_count=len(unmatched_forecasts),
    )
    return ForecastAccuracyResponse(
        period=AnalyticsPeriod(start=start, end=end),
        cutoff=CutoffDetails(effective_time=cutoff),
        forecast_history=ForecastHistoryDetails(
            publication_from=history_start,
            publication_to=cutoff,
            history_horizon_days=history_horizon_days,
        ),
        metrics=metrics,
        quality=quality,
        comparisons=matched.comparisons,
        assumptions=[
            "The cutoff is an analytical assumption, not an official Elexon market deadline.",
            "Forecast publish_time must be at or before the inclusive cutoff.",
            "Records match only by timezone-normalized delivery start_time; "
            "no filling or interpolation is used.",
            "Malformed source records fail the request, so invalid_record_count "
            "is zero in successful responses.",
            "Forecast history is bounded by forecast_history.publication_from; "
            "older publications are not included.",
        ],
    )


class AnalyticsService:
    def __init__(
        self,
        generation: GenerationService,
        max_range_days: int,
        forecast_history_days: int,
    ) -> None:
        self.generation = generation
        self.max_range_days = max_range_days
        self.forecast_history_days = forecast_history_days

    async def forecast_accuracy(
        self, start: datetime, end: datetime, cutoff: datetime
    ) -> ForecastAccuracyResponse:
        start, end = validate_date_range(start, end, self.max_range_days)
        try:
            cutoff = require_aware(cutoff, "cutoff")
        except ValueError as exc:
            raise InvalidDateRangeError(str(exc)) from exc
        # WINDFOR is queried by publication time. Add one second to the inclusive
        # cutoff, then enforce publish_time <= cutoff locally during selection.
        # Keeping the total window equal to the configured horizon preserves the
        # upstream range bound.
        history_end = cutoff + timedelta(seconds=1)
        history_start = history_end - timedelta(days=self.forecast_history_days)
        actual_response = await self.generation.actuals(start, end)
        forecast_response = await self.generation.forecasts(history_start, history_end)
        return analyze_records(
            actual_response.records,
            forecast_response.records,
            start,
            end,
            cutoff,
            history_start,
            self.forecast_history_days,
            self.max_range_days,
        )
