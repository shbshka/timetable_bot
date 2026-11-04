import re
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from config import INSTITUTION_TIMEZONE

ACADEMIC_HOUR = timedelta(minutes=45)
LECTURE_DURATION = timedelta(minutes=90)
_LECTURE_TIME_RE = re.compile(r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)")


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


def lecture_start_time(time_text: str) -> time | None:
    """
    Extract the start of a lecture from its time text, e.g. '08:30' or '08:30-10:00'.

    returns: the first HH:MM in the text, or None if it contains no times.
    """
    match = _LECTURE_TIME_RE.search(time_text)
    return time(int(match[1]), int(match[2])) if match else None


def add_lecture_end(time_text: str, academic_hours: float | None = None) -> str:
    """
    Turn a lone start time into a range using the lecture's duration, e.g. '08:30' with
    2 academic hours becomes '08:30-10:00'. Lectures without a duration are assumed to
    last LECTURE_DURATION.

    param time_text: the lecture time as stored.

    param academic_hours: the lecture's duration in academic hours, if known.

    returns: the range, or the text unchanged if it is anything but a single time.
    """
    match = _LECTURE_TIME_RE.fullmatch(time_text.strip())
    if not match:
        return time_text

    duration = academic_hours * ACADEMIC_HOUR if academic_hours else LECTURE_DURATION
    start = datetime.combine(date.min, time(int(match[1]), int(match[2])))
    return f"{match[0]}-{(start + duration).strftime('%H:%M')}"


def convert_lecture_time(time_text: str, lecture_date: date, timezone_name: str) -> str:
    """
    Convert every HH:MM in a lecture time from the institution timezone to the given one.

    Lecture times come from the sheets as text, e.g. '08:30' or '08:30-10:00'; anything
    around the times is kept. When the start of the lecture lands on another calendar day,
    the result is marked with the day offset, e.g. '00:30-02:00 (+1)'.

    param time_text: the lecture time as stored, in the institution timezone.

    param lecture_date: the lecture's date in the institution timezone.

    param timezone_name: the name of the timezone to convert to (e.g., 'Europe/London').

    returns: the time text in the specified timezone, unchanged if it contains no times.
    """
    tz = ZoneInfo(timezone_name)
    day_offsets = []

    def convert(match: re.Match) -> str:
        naive = datetime.combine(lecture_date, time(int(match[1]), int(match[2])))
        converted = resolve_local_time(naive, INSTITUTION_TIMEZONE.key).astimezone(tz)
        day_offsets.append((converted.date() - lecture_date).days)
        return converted.strftime("%H:%M")

    converted_text = _LECTURE_TIME_RE.sub(convert, time_text)

    if day_offsets and day_offsets[0]:
        return f"{converted_text} ({day_offsets[0]:+d})"
    return converted_text
