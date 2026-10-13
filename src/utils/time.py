from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from config import INSTITUTION_TIMEZONE


def utc_now() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(UTC)


def utc_today() -> date:
    """Return today's date in UTC."""
    return utc_now().date()


def institution_now() -> datetime:
    """Return the current time in the configured institution timezone."""
    return datetime.now(INSTITUTION_TIMEZONE)


def institution_today() -> date:
    """Return today's date in the configured institution timezone."""
    return institution_now().date()


def resolve_local_time(naive: datetime, timezone_name: str) -> datetime:
    """
    Convert a naive datetime to a timezone-aware datetime in the specified timezone, 
    handling ambiguous and non-existent times.

    param naive: a naive datetime object (without timezone info).
    
    param timezone_name: the name of the timezone to convert to (e.g., 'Europe/London').

    returns: a timezone-aware datetime object in the specified timezone.
    """
    tz = ZoneInfo(timezone_name)
    valid = {}
    normalized = []

    for fold in (0, 1):
        candidate = naive.replace(tzinfo=tz, fold=fold)
        instant = candidate.astimezone(UTC)
        back = instant.astimezone(tz)
        normalized.append(back)

        if back.replace(tzinfo=None) == naive:
            valid[instant] = back

    if valid:
        return valid[min(valid)]

    forward = [
        value for value in normalized
        if value.replace(tzinfo=None) > naive
    ]
    if not forward:
        raise ValueError(f"Cannot resolve local time: {naive}")

    return min(forward, key=lambda value: value.replace(tzinfo=None))
