from datetime import date, datetime
from zoneinfo import ZoneInfo

from src.parser.academic_year import academic_start_year
from src.utils import time


def test_institution_now_uses_configured_timezone(monkeypatch) -> None:
    monkeypatch.setattr(time, "INSTITUTION_TIMEZONE", ZoneInfo("Pacific/Kiritimati"))

    current = time.institution_now()

    assert current.tzinfo == ZoneInfo("Pacific/Kiritimati")


def test_institution_today_uses_institution_local_date(monkeypatch) -> None:
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, timezone=None):
            return cls(2026, 1, 2, 0, 30, tzinfo=timezone)

    monkeypatch.setattr(time, "datetime", FixedDateTime)

    assert time.institution_today() == date(2026, 1, 2)


def test_academic_year_uses_institution_today_when_date_is_omitted(monkeypatch) -> None:
    monkeypatch.setattr("src.parser.academic_year.institution_today", lambda: date(2026, 6, 30))

    assert academic_start_year() == 2025


def test_academic_year_uses_institution_today_when_date_is_omitted(monkeypatch):
    monkeypatch.setattr("src.parser.academic_year.institution_today", lambda: date(2026, 6, 30))
 
    assert academic_start_year() == 2025


def test_resolve_repeated_hour_chooses_first_occurrence() -> None:
    from datetime import UTC

    resolved = time.resolve_local_time(datetime(2026, 10, 25, 3, 30), "Europe/Vilnius")
    assert resolved.astimezone(UTC) == datetime(2026, 10, 25, 0, 30, tzinfo=UTC)
    assert resolved.fold == 0


def test_resolve_skipped_hour_moves_forward_preserving_minutes() -> None:
    from datetime import UTC

    resolved = time.resolve_local_time(datetime(2026, 3, 29, 3, 30), "Europe/Vilnius")
    assert resolved.replace(tzinfo=None) == datetime(2026, 3, 29, 4, 30)
    assert resolved.astimezone(UTC) == datetime(2026, 3, 29, 1, 30, tzinfo=UTC)


def test_resolve_non_dst_timezone_preserves_wall_time() -> None:
    from datetime import timedelta

    resolved = time.resolve_local_time(datetime(2026, 1, 1, 9, 15), "Asia/Yerevan")
    assert resolved.replace(tzinfo=None) == datetime(2026, 1, 1, 9, 15)
    assert resolved.utcoffset() == timedelta(hours=4)
