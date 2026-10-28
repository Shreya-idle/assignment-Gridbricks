import asyncio
import email.utils
import logging
import random
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.errors import (
    UpstreamAuthenticationError,
    UpstreamConnectionError,
    UpstreamNotFoundError,
    UpstreamRateLimitError,
    UpstreamResponseError,
    UpstreamServerError,
    UpstreamTimeoutError,
)
from app.utils.datetime import to_elexon_datetime

logger = logging.getLogger(__name__)


class ElexonClient:
    """Async client for public Elexon Insights raw dataset stream endpoints."""

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float,
        max_retries: int,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Any] = asyncio.sleep,
    ) -> None:
        timeout = httpx.Timeout(timeout_seconds, connect=min(timeout_seconds, 10.0))
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            transport=transport,
            headers={"Accept": "application/json", "User-Agent": "WindSight/0.1"},
        )
        self._max_retries = max_retries
        self._sleep = sleep

    async def __aenter__(self) -> "ElexonClient":
        return self

    async def __aexit__(self, *_args: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def fetch_actuals(self, start: datetime, end: datetime) -> list[dict[str, Any]]:
        return await self._fetch_dataset("FUELHH", start, end)

    async def fetch_forecasts(self, start: datetime, end: datetime) -> list[dict[str, Any]]:
        return await self._fetch_dataset("WINDFOR", start, end)

    async def _fetch_dataset(
        self, dataset: str, start: datetime, end: datetime
    ) -> list[dict[str, Any]]:
        params = {
            "publishDateTimeFrom": to_elexon_datetime(start),
            "publishDateTimeTo": to_elexon_datetime(end),
            "format": "json",
        }
        response = await self._request(f"/datasets/{dataset}/stream", params)
        content_type = response.headers.get("content-type", "").lower()
        if "json" not in content_type:
            raise UpstreamResponseError("Elexon returned an unexpected content type")
        try:
            payload = response.json()
        except ValueError as exc:
            raise UpstreamResponseError("Elexon returned malformed JSON") from exc
        # Stream endpoints normally return an array. Accept the documented JSON
        # envelope too, without exposing it to application code.
        if isinstance(payload, dict) and isinstance(payload.get("data"), list):
            payload = payload["data"]
        if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
            raise UpstreamResponseError("Elexon returned an unexpected response structure")
        return payload

    async def _request(self, path: str, params: dict[str, str]) -> httpx.Response:
        started = time.monotonic()
        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.get(path, params=params)
            except httpx.TimeoutException as exc:
                if attempt == self._max_retries:
                    raise UpstreamTimeoutError("Elexon request timed out") from exc
                await self._backoff(attempt, None)
                continue
            except httpx.RequestError as exc:
                if attempt == self._max_retries:
                    raise UpstreamConnectionError("Could not connect to Elexon") from exc
                await self._backoff(attempt, None)
                continue

            if response.status_code in (401, 403):
                raise UpstreamAuthenticationError("Elexon rejected the request")
            if response.status_code == 404:
                raise UpstreamNotFoundError("Elexon dataset endpoint was not found")
            if response.status_code == 429 or 500 <= response.status_code < 600:
                if attempt < self._max_retries:
                    logger.warning(
                        "Retrying Elexon request dataset_path=%s attempt=%d status=%d",
                        path,
                        attempt + 1,
                        response.status_code,
                    )
                    await self._backoff(attempt, response.headers.get("retry-after"))
                    continue
                if response.status_code == 429:
                    raise UpstreamRateLimitError("Elexon rate limit persisted after retries")
                raise UpstreamServerError("Elexon remained unavailable after retries")
            if response.is_error:
                raise UpstreamResponseError(
                    f"Elexon rejected the request with HTTP {response.status_code}"
                )
            logger.info(
                "Elexon request completed dataset_path=%s duration_ms=%d",
                path,
                round((time.monotonic() - started) * 1000),
            )
            return response
        raise AssertionError("retry loop exited unexpectedly")

    async def _backoff(self, attempt: int, retry_after: str | None) -> None:
        delay = self._retry_after_seconds(retry_after)
        if delay is None:
            delay = min(0.5 * (2**attempt) + random.uniform(0, 0.1), 10.0)
        await self._sleep(delay)

    @staticmethod
    def _retry_after_seconds(value: str | None) -> float | None:
        if not value:
            return None
        try:
            return max(0.0, min(float(value), 60.0))
        except ValueError:
            try:
                retry_at = email.utils.parsedate_to_datetime(value)
                return max(0.0, min((retry_at - datetime.now(UTC)).total_seconds(), 60.0))
            except (TypeError, ValueError):
                return None
