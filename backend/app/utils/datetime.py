from datetime import UTC, datetime, timedelta

from app.core.errors import InvalidDateRangeError


def require_aware(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include a timezone offset")
    return value.astimezone(UTC)


def validate_date_range(start: datetime, end: datetime, max_days: int) -> tuple[datetime, datetime]:
    try:
        start_utc = require_aware(start, "from")
        end_utc = require_aware(end, "to")
    except ValueError as exc:
        raise InvalidDateRangeError(str(exc)) from exc
    if start_utc >= end_utc:
        raise InvalidDateRangeError("'from' must be earlier than 'to'")
    if end_utc - start_utc > timedelta(days=max_days):
        raise InvalidDateRangeError(f"date range cannot exceed {max_days} days")
    return start_utc, end_utc


def to_elexon_datetime(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
