"""Parser for the four-week, horizontally repeated timetable export."""

from datetime import date, datetime, timedelta
import re
from typing import Optional

from config import STUDY_FORMS
from src.parser.academic_year import academic_start_year
from src.parser.interface import ParsedSchedule, ScheduleGrid
from src.parser.models import DaySchedule, Lecture
from src.utils.time import institution_today

_DATE_RE = re.compile(r"(?<!\d)(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?")
_TIME_RE = re.compile(r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)")
_COURSE_YEAR_RE = re.compile(r"\b(?:курс|course)\s*(\d+)\b", re.IGNORECASE)


def _value(grid: ScheduleGrid, row: int, column: int) -> str:
    if row >= len(grid) or column >= len(grid[row]):
        return ""
    return grid[row][column].get("value", "").strip()


def _note(grid: ScheduleGrid, row: int, column: int) -> str:
    if row >= len(grid) or column >= len(grid[row]):
        return ""
    return grid[row][column].get("note", "").strip()


def _find_header_blocks(grid: ScheduleGrid) -> list[tuple[int, int]]:
    blocks = []
    for row_index, row in enumerate(grid):
        for column, cell in enumerate(row):
            if cell.get("value", "").strip().lower() != "date":
                continue
            header = [_value(grid, row_index, column + offset).lower() for offset in range(6)]
            if header[1:6] == ["time", "room", "course", "teacher", "form"]:
                blocks.append((row_index, column))
    return blocks


def _course_year(grid: ScheduleGrid, header_row: int, start_column: int) -> Optional[int]:
    for row_index in range(max(0, header_row - 4), header_row):
        text = " ".join(_value(grid, row_index, column) for column in range(start_column, start_column + 6))
        match = _COURSE_YEAR_RE.search(text)
        if match:
            return int(match.group(1))
    return None


def _parse_date(value: str, academic_year: int, previous: Optional[date]) -> Optional[date]:
    match = _DATE_RE.search(value)
    if not match:
        return None
    day, month, year_text = (int(part) if part else None for part in match.groups())
    year = year_text if year_text is not None else academic_year
    if year < 100:
        year += 2000
    if year_text is None and previous and month < previous.month:
        year = previous.year + 1
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _duration_hours(value: str) -> Optional[float]:
    matches = _TIME_RE.findall(value)
    if len(matches) < 2:
        return None
    start = int(matches[0][0]) * 60 + int(matches[0][1])
    end = int(matches[1][0]) * 60 + int(matches[1][1])
    duration = (end - start) / 60
    return duration if duration > 0 else None


def _study_form(form: str) -> Optional[str]:
    normalized = form.strip().upper()
    return normalized if normalized in STUDY_FORMS else None


def parse_all_schedule_grid(grid: ScheduleGrid) -> list[Lecture]:
    academic_year = academic_start_year()
    lectures: list[Lecture] = []
    for header_row, start_column in _find_header_blocks(grid):
        course_year = _course_year(grid, header_row, start_column)
        current_date: Optional[date] = None
        for row_index in range(header_row + 1, len(grid)):
            date_value = _value(grid, row_index, start_column)
            parsed_date = _parse_date(date_value, academic_year, current_date)
            if parsed_date:
                current_date = parsed_date
            time_value = _value(grid, row_index, start_column + 1)
            subject = _value(grid, row_index, start_column + 3)
            if not current_date or not subject or not _TIME_RE.search(time_value):
                continue
            cell_note = _note(grid, row_index, start_column + 3)
            time = time_value or cell_note
            lectures.append(
                Lecture(
                    date=current_date,
                    time=time,
                    room=_value(grid, row_index, start_column + 2) or None,
                    subject=subject,
                    teacher=_value(grid, row_index, start_column + 4) or None,
                    form=_value(grid, row_index, start_column + 5) or None,
                    hours=_duration_hours(time),
                    course_year=course_year,
                    level=_study_form(_value(grid, row_index, start_column + 5)),
                    cell_note=cell_note or None,
                )
            )
    return lectures


def parse_schedule_grid(
    grid: ScheduleGrid,
    target_date: Optional[datetime] = None,
    fetch_full_week: bool = False,
) -> ParsedSchedule:
    lectures = parse_all_schedule_grid(grid)
    requested_date = target_date.date() if target_date else institution_today()
    if fetch_full_week:
        start_date = requested_date - timedelta(days=requested_date.weekday())
        dates = [start_date + timedelta(days=offset) for offset in range(7)]
    else:
        dates = [requested_date]
    return [
        DaySchedule(
            date=day,
            lectures=sorted(
                (lecture for lecture in lectures if lecture.date == day),
                key=lambda item: (item.time or "", item.subject),
            ),
        )
        for day in dates
    ]


class FourWeekGridParser:
    def parse_all(self, grid: ScheduleGrid) -> list[Lecture]:
        return parse_all_schedule_grid(grid)

    def parse(
        self,
        grid: ScheduleGrid,
        target_date: Optional[datetime] = None,
        fetch_full_week: bool = False,
    ) -> ParsedSchedule:
        return parse_schedule_grid(grid, target_date=target_date, fetch_full_week=fetch_full_week)