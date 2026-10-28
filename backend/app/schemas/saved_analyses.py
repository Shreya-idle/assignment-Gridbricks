import uuid
from datetime import datetime, timedelta

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SavedAnalysisFields(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    period_start: datetime
    period_end: datetime
    cutoff: datetime

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name must not be blank")
        return normalized

    @field_validator("period_start", "period_end", "cutoff")
    @classmethod
    def require_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_period(self) -> "SavedAnalysisFields":
        if self.period_start >= self.period_end:
            raise ValueError("period_start must be before period_end")
        if self.period_end - self.period_start > timedelta(days=7):
            raise ValueError("analysis period cannot exceed seven days")
        return self


class SavedAnalysisCreate(SavedAnalysisFields):
    pass


class SavedAnalysisUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name must not be blank")
        return normalized


class SavedAnalysisResponse(SavedAnalysisFields):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
