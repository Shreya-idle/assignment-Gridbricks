import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.models import SavedAnalysisConfiguration
from app.schemas.saved_analyses import (
    SavedAnalysisCreate,
    SavedAnalysisResponse,
    SavedAnalysisUpdate,
)
from app.services.auth import AuthenticatedUser, require_permanent_user

router = APIRouter(prefix="/saved-analyses", tags=["saved analyses"])


@router.get("", response_model=list[SavedAnalysisResponse])
async def list_saved_analyses(
    user: Annotated[AuthenticatedUser, Depends(require_permanent_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[SavedAnalysisConfiguration]:
    try:
        result = await session.scalars(
            select(SavedAnalysisConfiguration)
            .where(SavedAnalysisConfiguration.user_identifier == str(user.id))
            .order_by(SavedAnalysisConfiguration.updated_at.desc())
        )
        return list(result)
    except SQLAlchemyError:
        raise _database_unavailable() from None


@router.post("", response_model=SavedAnalysisResponse, status_code=status.HTTP_201_CREATED)
async def create_saved_analysis(
    payload: SavedAnalysisCreate,
    user: Annotated[AuthenticatedUser, Depends(require_permanent_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SavedAnalysisConfiguration:
    item = SavedAnalysisConfiguration(user_identifier=str(user.id), **payload.model_dump())
    try:
        session.add(item)
        await session.commit()
        await session.refresh(item)
        return item
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=409, detail="A saved analysis with this name already exists"
        ) from None
    except SQLAlchemyError:
        await session.rollback()
        raise _database_unavailable() from None


@router.patch("/{analysis_id}", response_model=SavedAnalysisResponse)
async def rename_saved_analysis(
    analysis_id: uuid.UUID,
    payload: SavedAnalysisUpdate,
    user: Annotated[AuthenticatedUser, Depends(require_permanent_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SavedAnalysisConfiguration:
    try:
        await session.execute(
            update(SavedAnalysisConfiguration)
            .where(
                SavedAnalysisConfiguration.id == analysis_id,
                SavedAnalysisConfiguration.user_identifier == str(user.id),
            )
            .values(name=payload.name)
        )
        await session.commit()
        item = await session.scalar(
            select(SavedAnalysisConfiguration).where(
                SavedAnalysisConfiguration.id == analysis_id,
                SavedAnalysisConfiguration.user_identifier == str(user.id),
            )
        )
        if item is None:
            raise HTTPException(status_code=404, detail="Saved analysis not found")
        return item
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=409, detail="A saved analysis with this name already exists"
        ) from None
    except SQLAlchemyError:
        await session.rollback()
        raise _database_unavailable() from None


@router.delete("/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_analysis(
    analysis_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(require_permanent_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    try:
        result = await session.execute(
            delete(SavedAnalysisConfiguration).where(
                SavedAnalysisConfiguration.id == analysis_id,
                SavedAnalysisConfiguration.user_identifier == str(user.id),
            )
        )
        if result.rowcount == 0:
            await session.rollback()
            raise HTTPException(status_code=404, detail="Saved analysis not found")
        await session.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except SQLAlchemyError:
        await session.rollback()
        raise _database_unavailable() from None


def _database_unavailable() -> HTTPException:
    return HTTPException(status_code=503, detail="Saved analyses are temporarily unavailable")
