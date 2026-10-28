import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    name: str
    version: str
    status: Literal["ok"] = "ok"
    environment: str


class DatabaseHealthResponse(BaseModel):
    status: Literal["connected"] = "connected"


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    settings = request.app.state.settings
    return HealthResponse(
        name=settings.app_name,
        version=settings.app_version,
        environment=settings.app_env,
    )


@router.get("/health/database", response_model=DatabaseHealthResponse)
async def database_health(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DatabaseHealthResponse:
    try:
        await session.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.warning("Database health check failed error_type=%s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable",
        ) from exc
    return DatabaseHealthResponse()
