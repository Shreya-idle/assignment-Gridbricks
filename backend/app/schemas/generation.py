import math
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

from app.utils.datetime import require_aware


class GenerationBase(BaseModel):
    model_config = ConfigDict(extra="ignore")

    start_time: datetime
    generation: float

    @field_validator("start_time")
    @classmethod
    def validate_start_time(cls, value: datetime) -> datetime:
        return require_aware(value, "start_time")

    @field_validator("generation")
    @classmethod
    def validate_generation(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("generation must be finite")
        return value


class ActualGenerationRecord(GenerationBase):
    fuel_type: Literal["WIND"] = "WIND"
    source: Literal["FUELHH"] = "FUELHH"


class ForecastGenerationRecord(GenerationBase):
    publish_time: datetime
    source: Literal["WINDFOR"] = "WINDFOR"

    @field_validator("publish_time")
    @classmethod
    def validate_publish_time(cls, value: datetime) -> datetime:
        return require_aware(value, "publish_time")


class RawActualRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    fuel_type: str
    start_time: datetime
    generation: float


class RawForecastRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    start_time: datetime
    publish_time: datetime
    generation: float
