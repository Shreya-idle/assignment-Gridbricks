from datetime import datetime
from typing import Literal

from pydantic import BaseModel

RetrievalStatus = Literal["not_checked", "healthy", "unavailable", "error"]


class SourceMetadata(BaseModel):
    dataset: Literal["FUELHH", "WINDFOR"]
    documentation_url: str
    configured: bool
    last_successful_retrieval: datetime | None = None
    last_retrieval_status: RetrievalStatus = "not_checked"
    last_error_summary: str | None = None
    last_record_count: int | None = None
