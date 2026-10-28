from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_generation_service
from app.schemas.generation import ActualGenerationRecord, ForecastGenerationRecord
from app.schemas.responses import GenerationResponse
from app.services.generation import GenerationService

router = APIRouter(prefix="/generation", tags=["generation"])


@router.get("/actuals", response_model=GenerationResponse[ActualGenerationRecord])
async def actuals(
    start: Annotated[datetime, Query(alias="from", description="Inclusive UTC-aware boundary")],
    end: Annotated[datetime, Query(alias="to", description="Exclusive UTC-aware boundary")],
    service: Annotated[GenerationService, Depends(get_generation_service)],
) -> GenerationResponse[ActualGenerationRecord]:
    return await service.actuals(start, end)


@router.get("/forecasts", response_model=GenerationResponse[ForecastGenerationRecord])
async def forecasts(
    start: Annotated[datetime, Query(alias="from", description="Inclusive publication boundary")],
    end: Annotated[datetime, Query(alias="to", description="Exclusive publication boundary")],
    service: Annotated[GenerationService, Depends(get_generation_service)],
) -> GenerationResponse[ForecastGenerationRecord]:
    return await service.forecasts(start, end)
