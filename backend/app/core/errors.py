from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class WindSightError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class InvalidDateRangeError(WindSightError):
    status_code = 422
    code = "invalid_date_range"


class UpstreamError(WindSightError):
    status_code = 502
    code = "upstream_error"


class UpstreamTimeoutError(UpstreamError):
    status_code = 504
    code = "upstream_timeout"


class UpstreamConnectionError(UpstreamError):
    status_code = 503
    code = "upstream_connection_error"


class UpstreamAuthenticationError(UpstreamError):
    code = "upstream_authentication_error"


class UpstreamNotFoundError(UpstreamError):
    code = "upstream_not_found"


class UpstreamRateLimitError(UpstreamError):
    status_code = 503
    code = "upstream_rate_limited"


class UpstreamServerError(UpstreamError):
    status_code = 503
    code = "upstream_unavailable"


class UpstreamResponseError(UpstreamError):
    code = "invalid_upstream_response"


class InvalidSourceRecordError(UpstreamResponseError):
    code = "invalid_source_record"


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(WindSightError)
    async def handle_known_error(_request: Request, exc: WindSightError) -> JSONResponse:
        payload: dict[str, Any] = {"error": {"code": exc.code, "message": exc.message}}
        return JSONResponse(status_code=exc.status_code, content=payload)
