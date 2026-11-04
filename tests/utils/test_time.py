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


def test_add_lecture_end_adds_standard_duration_to_lone_start() -> None:
    assert time.add_lecture_end("08:30") == "08:30-10:00"
    assert time.add_lecture_end(" 8:30 ") == "8:30-10:00"


def test_add_lecture_end_wraps_past_midnight() -> None:
    assert time.add_lecture_end("23:30") == "23:30-01:00"


def test_add_lecture_end_leaves_ranges_and_free_text() -> None:
    assert time.add_lecture_end("08:30-11:00") == "08:30-11:00"
    assert time.add_lecture_end("from 08:30") == "from 08:30"


def test_add_lecture_end_uses_lecture_duration_in_academic_hours() -> None:
    assert time.add_lecture_end("08:30", 2) == "08:30-10:00"
    assert time.add_lecture_end("08:30", 3) == "08:30-10:45"
    assert time.add_lecture_end("08:30", 4.0) == "08:30-11:30"


def test_add_lecture_end_falls_back_to_standard_duration_without_hours() -> None:
    assert time.add_lecture_end("08:30", None) == "08:30-10:00"
    assert time.add_lecture_end("08:30", 0) == "08:30-10:00"


def test_add_lecture_end_keeps_range_from_sheet_whatever_the_duration() -> None:
    assert time.add_lecture_end("08:30-11:00", 2) == "08:30-11:00"


def _vilnius_institution(monkeypatch) -> None:
    monkeypatch.setattr(time, "INSTITUTION_TIMEZONE", ZoneInfo("Europe/Vilnius"))


def test_convert_lecture_time_converts_single_time_and_range(monkeypatch) -> None:
    _vilnius_institution(monkeypatch)

    assert time.convert_lecture_time("08:30", date(2026, 10, 5), "Asia/Almaty") == "10:30"
    assert time.convert_lecture_time("08:30-10:00", date(2026, 10, 5), "Europe/London") == "06:30-08:00"


def test_convert_lecture_time_keeps_institution_timezone_unchanged(monkeypatch) -> None:
    _vilnius_institution(monkeypatch)

    assert time.convert_lecture_time("08:30-10:00", date(2026, 10, 5), "Europe/Vilnius") == "08:30-10:00"


def test_convert_lecture_time_follows_dst_of_lecture_date(monkeypatch) -> None:
    _vilnius_institution(monkeypatch)

    # Vilnius is UTC+3 in summer and UTC+2 in winter; Yerevan is UTC+4 all year.
    assert time.convert_lecture_time("08:30", date(2026, 7, 1), "Asia/Yerevan") == "09:30"
    assert time.convert_lecture_time("08:30", date(2026, 12, 1), "Asia/Yerevan") == "10:30"


def test_convert_lecture_time_marks_other_calendar_day(monkeypatch) -> None:
    _vilnius_institution(monkeypatch)

    assert time.convert_lecture_time("21:30-23:00", date(2026, 12, 1), "Asia/Yekaterinburg") == "00:30-02:00 (+1)"
    assert time.convert_lecture_time("01:00", date(2026, 12, 1), "Europe/London") == "23:00 (-1)"


def test_convert_lecture_time_marks_day_by_lecture_start_only(monkeypatch) -> None:
    _vilnius_institution(monkeypatch)

    assert time.convert_lecture_time("20:00-21:30", date(2026, 12, 1), "Asia/Yekaterinburg") == "23:00-00:30"


def test_convert_lecture_time_leaves_text_without_times(monkeypatch) -> None:
    _vilnius_institution(monkeypatch)

    assert time.convert_lecture_time("see 12.10 note", date(2026, 10, 5), "Asia/Almaty") == "see 12.10 note"
