from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_source_statuses
from app.schemas.data_sources import SourceMetadata
from app.services.source_status import SourceStatusRegistry

router = APIRouter(tags=["data sources"])


@router.get("/data-sources", response_model=list[SourceMetadata])
async def data_sources(
    statuses: Annotated[SourceStatusRegistry, Depends(get_source_statuses)],
) -> list[SourceMetadata]:
    return statuses.list()
