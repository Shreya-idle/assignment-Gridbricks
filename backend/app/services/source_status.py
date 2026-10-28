from datetime import UTC, datetime

from app.schemas.data_sources import SourceMetadata

DOCS = {
    "FUELHH": "https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream",
    "WINDFOR": "https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/WINDFOR/stream",
}


class SourceStatusRegistry:
    def __init__(self, configured: bool) -> None:
        self._sources = {
            dataset: SourceMetadata(dataset=dataset, documentation_url=url, configured=configured)
            for dataset, url in DOCS.items()
        }

    def list(self) -> list[SourceMetadata]:
        return [item.model_copy(deep=True) for item in self._sources.values()]

    def success(self, dataset: str, count: int) -> None:
        item = self._sources[dataset]
        item.last_successful_retrieval = datetime.now(UTC)
        item.last_retrieval_status = "healthy"
        item.last_error_summary = None
        item.last_record_count = count

    def failure(self, dataset: str, summary: str) -> None:
        item = self._sources[dataset]
        item.last_retrieval_status = "unavailable"
        item.last_error_summary = summary
