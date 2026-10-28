from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_analytics_service
from app.schemas.analytics import ForecastAccuracyResponse
from app.services.analytics import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/forecast-accuracy", response_model=ForecastAccuracyResponse)
async def forecast_accuracy(
    start: Annotated[datetime, Query(alias="from", description="Inclusive delivery boundary")],
    end: Annotated[datetime, Query(alias="to", description="Exclusive delivery boundary")],
    cutoff: Annotated[
        datetime,
        Query(description="Inclusive forecast publication cutoff; timezone offset is required"),
    ],
    service: Annotated[AnalyticsService, Depends(get_analytics_service)],
) -> ForecastAccuracyResponse:
    """Compare actuals with the latest forecast eligible at the publication cutoff."""
    return await service.forecast_accuracy(start, end, cutoff)
