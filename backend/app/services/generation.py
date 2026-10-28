import logging
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from app.clients.elexon import ElexonClient
from app.core.errors import InvalidSourceRecordError, WindSightError
from app.schemas.generation import ActualGenerationRecord, ForecastGenerationRecord
from app.schemas.responses import GenerationResponse, RetrievalMetadata
from app.services.persistence import PersistenceService
from app.services.source_status import SourceStatusRegistry
from app.utils.datetime import validate_date_range

logger = logging.getLogger(__name__)


class GenerationService:
    def __init__(
        self,
        client: ElexonClient,
        statuses: SourceStatusRegistry,
        max_range_days: int,
        persistence: PersistenceService | None = None,
    ) -> None:
        self.client = client
        self.statuses = statuses
        self.max_range_days = max_range_days
        self.persistence = persistence or PersistenceService(None)

    async def actuals(
        self, start: datetime, end: datetime
    ) -> GenerationResponse[ActualGenerationRecord]:
        start, end = validate_date_range(start, end, self.max_range_days)
        run_id = await self.persistence.start_run("FUELHH", start, end)
        logger.info("Retrieving FUELHH from=%s to=%s", start.isoformat(), end.isoformat())
        try:
            raw = await self.client.fetch_actuals(start, end)
            records = [
                record
                for record in self._normalize_actuals(raw)
                if start <= record.start_time < end
            ]
        except WindSightError as exc:
            self.statuses.failure("FUELHH", exc.code)
            await self.persistence.fail_run(run_id, "FUELHH", exc.code)
            raise
        self.statuses.success("FUELHH", len(records))
        await self.persistence.complete_actuals(run_id, records)
        return self._response("FUELHH", start, end, records)

    async def forecasts(
        self, start: datetime, end: datetime
    ) -> GenerationResponse[ForecastGenerationRecord]:
        start, end = validate_date_range(start, end, self.max_range_days)
        run_id = await self.persistence.start_run("WINDFOR", start, end)
        logger.info("Retrieving WINDFOR from=%s to=%s", start.isoformat(), end.isoformat())
        try:
            raw = await self.client.fetch_forecasts(start, end)
            records = self._normalize_forecasts(raw)
        except WindSightError as exc:
            self.statuses.failure("WINDFOR", exc.code)
            await self.persistence.fail_run(run_id, "WINDFOR", exc.code)
            raise
        self.statuses.success("WINDFOR", len(records))
        await self.persistence.complete_forecasts(run_id, records)
        return self._response("WINDFOR", start, end, records)

    @staticmethod
    def _normalize_actuals(raw: list[dict[str, Any]]) -> list[ActualGenerationRecord]:
        records: list[ActualGenerationRecord] = []
        invalid = 0
        for item in raw:
            if str(item.get("fuelType", "")).upper() != "WIND":
                continue
            try:
                records.append(
                    ActualGenerationRecord(
                        start_time=item.get("startTime"),
                        generation=item.get("generation"),
                    )
                )
            except ValidationError:
                invalid += 1
        if invalid:
            logger.warning("FUELHH validation failures count=%d", invalid)
            raise InvalidSourceRecordError(f"FUELHH contained {invalid} invalid wind record(s)")
        return records

    @staticmethod
    def _normalize_forecasts(raw: list[dict[str, Any]]) -> list[ForecastGenerationRecord]:
        records: list[ForecastGenerationRecord] = []
        invalid = 0
        for item in raw:
            try:
                records.append(
                    ForecastGenerationRecord(
                        start_time=item.get("startTime"),
                        publish_time=item.get("publishTime"),
                        generation=item.get("generation"),
                    )
                )
            except ValidationError:
                invalid += 1
        if invalid:
            logger.warning("WINDFOR validation failures count=%d", invalid)
            raise InvalidSourceRecordError(f"WINDFOR contained {invalid} invalid record(s)")
        return records

    @staticmethod
    def _response(dataset: str, start: datetime, end: datetime, records: list[Any]) -> Any:
        return GenerationResponse(
            requested_from=start,
            requested_to=end,
            dataset=dataset,
            record_count=len(records),
            records=records,
            retrieval=RetrievalMetadata(retrieved_at=datetime.now(UTC)),
        )
