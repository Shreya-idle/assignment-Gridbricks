from datetime import datetime
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel

from app.schemas.generation import ActualGenerationRecord, ForecastGenerationRecord

RecordT = TypeVar("RecordT", ActualGenerationRecord, ForecastGenerationRecord)


class RetrievalMetadata(BaseModel):
    retrieved_at: datetime
    upstream_status: Literal["success"] = "success"


class GenerationResponse(BaseModel, Generic[RecordT]):
    requested_from: datetime
    requested_to: datetime
    dataset: Literal["FUELHH", "WINDFOR"]
    record_count: int
    records: list[RecordT]
    retrieval: RetrievalMetadata
