import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import (
    ActualGenerationRecordModel,
    ForecastPublicationRecordModel,
    IngestionRun,
)
from app.schemas.generation import ActualGenerationRecord, ForecastGenerationRecord

logger = logging.getLogger(__name__)


class PersistenceService:
    """Best-effort storage that never changes live Elexon response semantics."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession] | None) -> None:
        self.session_factory = session_factory

    async def start_run(
        self, dataset: str, requested_from: datetime, requested_to: datetime
    ) -> uuid.UUID | None:
        if self.session_factory is None:
            return None
        run_id = uuid.uuid4()
        try:
            async with self.session_factory() as session, session.begin():
                session.add(
                    IngestionRun(
                        id=run_id,
                        dataset=dataset,
                        requested_from=requested_from,
                        requested_to=requested_to,
                        status="running",
                    )
                )
            return run_id
        except SQLAlchemyError as exc:
            self._log_failure("start_run", dataset, exc)
            return None

    async def complete_actuals(
        self, run_id: uuid.UUID | None, records: list[ActualGenerationRecord]
    ) -> None:
        if self.session_factory is None or run_id is None:
            return
        values = [
            {
                "id": uuid.uuid4(),
                "delivery_time": item.start_time,
                "generation": item.generation,
                "source": item.source,
                "ingestion_run_id": run_id,
            }
            for item in records
        ]
        await self._complete(
            run_id,
            "FUELHH",
            ActualGenerationRecordModel,
            values,
            "uq_actual_source_delivery_generation",
            len(records),
        )

    async def complete_forecasts(
        self, run_id: uuid.UUID | None, records: list[ForecastGenerationRecord]
    ) -> None:
        if self.session_factory is None or run_id is None:
            return
        values = [
            {
                "id": uuid.uuid4(),
                "delivery_time": item.start_time,
                "publication_time": item.publish_time,
                "generation": item.generation,
                "source": item.source,
                "ingestion_run_id": run_id,
            }
            for item in records
        ]
        await self._complete(
            run_id,
            "WINDFOR",
            ForecastPublicationRecordModel,
            values,
            "uq_forecast_source_delivery_publication_generation",
            len(records),
        )

    async def _complete(
        self,
        run_id: uuid.UUID,
        dataset: str,
        model: type[ActualGenerationRecordModel] | type[ForecastPublicationRecordModel],
        values: list[dict],
        constraint: str,
        received_count: int,
    ) -> None:
        assert self.session_factory is not None
        try:
            async with self.session_factory() as session, session.begin():
                persisted_count = 0
                if values:
                    result = await session.execute(
                        insert(model).values(values).on_conflict_do_nothing(constraint=constraint)
                    )
                    persisted_count = max(result.rowcount or 0, 0)
                await session.execute(
                    update(IngestionRun)
                    .where(IngestionRun.id == run_id)
                    .values(
                        status="succeeded",
                        completed_at=datetime.now(UTC),
                        received_count=received_count,
                        persisted_count=persisted_count,
                        error_code=None,
                    )
                )
        except SQLAlchemyError as exc:
            self._log_failure("complete_run", dataset, exc)
            await self.fail_run(run_id, dataset, "database_persistence_failed")

    async def fail_run(self, run_id: uuid.UUID | None, dataset: str, error_code: str) -> None:
        if self.session_factory is None or run_id is None:
            return
        try:
            async with self.session_factory() as session, session.begin():
                await session.execute(
                    update(IngestionRun)
                    .where(IngestionRun.id == run_id)
                    .values(
                        status="failed",
                        completed_at=datetime.now(UTC),
                        error_code=error_code[:64],
                    )
                )
        except SQLAlchemyError as exc:
            self._log_failure("fail_run", dataset, exc)

    @staticmethod
    def _log_failure(operation: str, dataset: str, exc: SQLAlchemyError) -> None:
        logger.warning(
            "Database persistence unavailable operation=%s dataset=%s error_type=%s",
            operation,
            dataset,
            type(exc).__name__,
        )
