from datetime import date, datetime

from src.parser.models import DaySchedule, Lecture
from src.utils.formatter import format_daily_schedule, format_weekly_schedule


def test_schedule_formatters_emit_html_and_escape_lecture_values() -> None:
    # Arrange
    lecture_date = date(2026, 10, 5)
    schedule = [
        DaySchedule(
            date=lecture_date,
            lectures=[
                Lecture(
                    date=lecture_date,
                    time="08:30-10:00",
                    subject="Algorithms <advanced>",
                    teacher="A & B",
                    form="HR",
                )
            ],
        )
    ]

    # Act
    daily = format_daily_schedule("24HR", datetime(2026, 10, 5), schedule, locale="en")
    weekly = format_weekly_schedule("24HR", schedule, locale="en")

    # Assert
    assert "<code>08:30-10:00</code>" in daily
    assert "<b>Algorithms &lt;advanced&gt;</b>" in daily
    assert "<i>A &amp; B</i>" in daily
    assert "<b>monday, 05 October</b>" in weekly