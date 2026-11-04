from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from src.parser.models import DaySchedule, Lecture
from src.utils import time
from src.utils.formatter import format_daily_schedule, format_weekly_schedule


@pytest.fixture(autouse=True)
def vilnius_institution(monkeypatch) -> None:
    monkeypatch.setattr(time, "INSTITUTION_TIMEZONE", ZoneInfo("Europe/Vilnius"))


def test_schedule_formatters_emit_html_and_escape_lecture_values() -> None:
    # Arrange
    lecture_date = date(2026, 10, 5)
    schedule = [
        DaySchedule(
            date=lecture_date,
            lectures=[
                Lecture(
                    date=lecture_date,
                    time="08:30",
                    subject="Algorithms <advanced>",
                    teacher="A & B",
                    form="HR",
                )
            ],
        )
    ]

    # Act
    daily = format_daily_schedule("24HR", datetime(2026, 10, 5), schedule, "Europe/Vilnius", locale="en")
    weekly = format_weekly_schedule("24HR", schedule, "Europe/Vilnius", locale="en")

    # Assert
    assert "<code>08:30-10:00</code>" in daily
    assert "<b>Algorithms &lt;advanced&gt;</b>" in daily
    assert "<i>A &amp; B</i>" in daily
    assert "<b>monday, 05 October</b>" in weekly


def _schedule_with_lecture(lecture_time: str | None) -> list[DaySchedule]:
    lecture_date = date(2026, 10, 5)
    return [
        DaySchedule(
            date=lecture_date,
            lectures=[Lecture(date=lecture_date, time=lecture_time, subject="Algorithms")],
        )
    ]


def test_schedule_formatters_show_times_in_chosen_timezone() -> None:
    # Arrange
    schedule = _schedule_with_lecture("08:30-10:00")

    # Act
    daily = format_daily_schedule("24HR", datetime(2026, 10, 5), schedule, "Asia/Almaty", locale="en")
    weekly = format_weekly_schedule("24HR", schedule, "Europe/London", locale="en")

    # Assert
    assert "<code>10:30-12:00</code> Almaty |" in daily
    assert "<code>06:30-08:00</code> London (GMT/BST) |" in weekly
    assert "Vilnius" not in daily + weekly


def test_schedule_formatter_keeps_placeholder_for_lecture_without_time() -> None:
    # Act
    daily = format_daily_schedule("24HR", datetime(2026, 10, 5), _schedule_with_lecture(None), "Asia/Almaty", locale="en")

    # Assert
    assert "<code>" in daily
    assert "Algorithms" in daily


def test_schedule_formatter_falls_back_to_timezone_name_without_label() -> None:
    # Act
    daily = format_daily_schedule("24HR", datetime(2026, 10, 5), _schedule_with_lecture("08:30"), "Asia/Tokyo", locale="en")

    # Assert
    assert "<code>14:30-16:00</code> Asia/Tokyo |" in daily


def test_schedule_formatter_end_time_matches_displayed_duration() -> None:
    # Arrange
    lecture_date = date(2026, 10, 5)
    schedule = [
        DaySchedule(
            date=lecture_date,
            lectures=[Lecture(date=lecture_date, time="08:30", subject="Algorithms", hours=4)],
        )
    ]

    # Act
    daily = format_daily_schedule("24HR", datetime(2026, 10, 5), schedule, "Asia/Almaty", locale="en")

    # Assert
    assert "<code>10:30-13:30</code>" in daily
    assert "(3 " in daily


def test_schedule_formatter_keeps_end_time_from_sheet() -> None:
    # Act
    daily = format_daily_schedule("24HR", datetime(2026, 10, 5), _schedule_with_lecture("08:30-11:00"), "Europe/Vilnius", locale="en")

    # Assert
    assert "<code>08:30-11:00</code>" in daily