from datetime import date, datetime, timedelta
import re
from typing import Dict, List, Optional

from src.parser.interface import ParsedSchedule, ScheduleGrid
from src.parser.academic_year import academic_start_year
from src.parser.models import DaySchedule, Lecture
from src.utils.time import institution_today

_WEEK_HEADER_RE = re.compile(r"W\d+", re.IGNORECASE)
_TIME_RE = re.compile(r"(?<!\d)([01]?\d|2[0-3])[.:]([0-5]\d)(?!\d)")
_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def _value(grid: ScheduleGrid, row: int, column: int) -> str:
    if row >= len(grid) or column >= len(grid[row]):
        return ""
    return grid[row][column].get("value", "").strip()


def _month_numbers(label: str) -> List[int]:
    months = []
    for part in re.split(r"[/\s-]+", label.lower()):
        for abbreviation, month in _MONTHS.items():
            if part.startswith(abbreviation):
                months.append(month)
                break
    return months


def _date_columns(grid: ScheduleGrid) -> Dict[int, date]:
    if len(grid) < 3:
        return {}

    week_row = grid[0]
    date_row = grid[1]
    month_row = grid[2]
    first_column = next(
        (
            column
            for column, cell in enumerate(week_row)
            if _WEEK_HEADER_RE.fullmatch(cell.get("value", "").strip())
        ),
        11,
    )
    last_column = max(len(week_row), len(date_row), len(month_row))
    month_for_column: Dict[int, int] = {}
    for block_start in range(first_column, last_column, 7):
        label = _value(grid, 2, block_start)
        months = _month_numbers(label)
        if not months:
            continue

        block_days = []
        for column in range(block_start, min(block_start + 7, last_column)):
            day_text = _value(grid, 1, column)
            block_days.append((column, int(day_text) if day_text.isdigit() else None))

        if len(months) == 1:
            for column, day_number in block_days:
                if day_number is not None:
                    month_for_column[column] = months[0]
            continue

        reset_columns = {
            column
            for (column, previous_day), (next_column, next_day) in zip(block_days, block_days[1:])
            if previous_day is not None and next_day is not None and next_day < previous_day
            for column in [next_column]
        }
        first_day = next((day_number for _, day_number in block_days if day_number is not None), None)
        leading_blank = next(
            (index for index, (_, day_number) in enumerate(block_days) if day_number is not None),
            0,
        ) > 0
        month_index = 0 if reset_columns or first_day is None or first_day > 7 or not leading_blank else 1
        for column, day_number in block_days:
            if day_number is None:
                continue
            if column in reset_columns:
                month_index = 1
            month_for_column[column] = months[min(month_index, len(months) - 1)]

    anchors = []
    year = academic_start_year()
    previous_month = None
    for column in range(first_column, last_column):
        day_text = _value(grid, 1, column)
        month = month_for_column.get(column)
        if month is None or not day_text.isdigit():
            continue
        day_number = int(day_text)
        if previous_month is not None and month < previous_month:
            year += 1
        try:
            anchors.append((column, date(year, month, day_number)))
        except ValueError:
            continue
        previous_month = month

    if not anchors:
        return {}

    dates: Dict[int, date] = {}
    first_anchor_column, first_anchor_date = anchors[0]
    for column in range(first_column, first_anchor_column):
        dates[column] = first_anchor_date - timedelta(days=first_anchor_column - column)

    previous_column, previous_date = anchors[0]
    dates[previous_column] = previous_date
    for column, current_date in anchors[1:]:
        for missing_column in range(previous_column + 1, column):
            dates[missing_column] = previous_date + timedelta(days=missing_column - previous_column)
        dates[column] = current_date
        previous_column, previous_date = column, current_date

    for column in range(previous_column + 1, last_column):
        dates[column] = previous_date + timedelta(days=column - previous_column)
    return dates


def _hours(value: str) -> Optional[float]:
    try:
        hours = float(value.replace(",", "."))
    except ValueError:
        return None
    return hours if hours > 0 else None


def _normalized_time(note: str) -> Optional[str]:
    matches = [f"{hour.zfill(2)}:{minute}" for hour, minute in _TIME_RE.findall(note)]
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]
    intervals = [f"{matches[index]}-{matches[index + 1]}" for index in range(0, len(matches) - 1, 2)]
    if len(matches) % 2:
        intervals.append(matches[-1])
    return ", ".join(intervals)


def _course_year(value: str) -> Optional[int]:
    match = re.match(r"\s*(\d+)\s*(?:\D.*)?$", value)
    return int(match.group(1)) if match else None


def parse_schedule_grid(
    grid: ScheduleGrid,
    target_date: Optional[datetime] = None,
    fetch_full_week: bool = False,
) -> ParsedSchedule:
    """Parse and select one date or calendar week from this timetable layout."""
    lectures = parse_all_schedule_grid(grid)
    if not lectures:
        return []

    if fetch_full_week:
        anchor_date = target_date.date() if target_date else institution_today()
        week_start = anchor_date - timedelta(days=anchor_date.weekday())
        return [
            DaySchedule(
                date=week_start + timedelta(days=offset),
                lectures=sorted(
                    (lecture for lecture in lectures if lecture.date == week_start + timedelta(days=offset)),
                    key=lambda lecture: (lecture.time or "", lecture.subject),
                ),
            )
            for offset in range(7)
        ]

    requested_date = target_date.date() if target_date else institution_today()
    return [
        DaySchedule(
            date=requested_date,
            lectures=sorted(
                (lecture for lecture in lectures if lecture.date == requested_date),
                key=lambda lecture: (lecture.time or "", lecture.subject),
            ),
        )
    ]


def parse_all_schedule_grid(grid: ScheduleGrid) -> List[Lecture]:
    """Parse every scheduled cell, preserving its course-year and delivery metadata."""
    if not grid:
        return []

    date_by_column = _date_columns(grid)
    if not date_by_column:
        return []

    first_date_column = min(date_by_column)
    active_year: Optional[int] = None
    active_subject: Optional[str] = None
    active_form: Optional[str] = None
    active_level: Optional[str] = None
    active_mode: Optional[str] = None
    active_course_notes: Optional[str] = None
    lectures: List[Lecture] = []

    for row_index in range(3, len(grid)):
        row = grid[row_index]
        values = [cell.get("value", "").strip() for cell in row]
        year_text = values[0] if values else ""
        subject = values[1] if len(values) > 1 else ""
        form = values[2] if len(values) > 2 else ""

        if not subject:
            section_year = _course_year(year_text)
            if section_year is not None and form == "" and not any(
                _value(grid, row_index, column) for column in date_by_column
            ):
                active_year = section_year
                active_subject = None
                active_form = None
                active_level = None
                active_mode = None
                active_course_notes = None
                continue
            if not active_subject:
                continue
        else:
            active_subject = subject
            active_year = _course_year(year_text) or active_year

        if len(values) > 2:
            active_form = values[2]
        if len(values) > 3 and values[3]:
            active_level = values[3]
        if len(values) > 4 and values[4]:
            active_mode = values[4]
        row_notes = [value for value in values[5:10] if value]
        if row_notes:
            active_course_notes = " | ".join(row_notes)

        if not active_subject:
            continue
        for column in range(first_date_column, len(row)):
            session_hours = _hours(values[column]) if column < len(values) else None
            if session_hours is None or column not in date_by_column:
                continue
            cell_note = row[column].get("note", "").strip()
            lectures.append(
                Lecture(
                    date=date_by_column[column],
                    time=_normalized_time(cell_note),
                    subject=active_subject,
                    form=active_form,
                    hours=session_hours,
                    course_year=active_year,
                    level=active_level,
                    delivery_mode=active_mode,
                    course_notes=active_course_notes,
                    cell_note=cell_note or None,
                )
            )

    return lectures


class AwfulUniGridParser:
    """Parser for the university's current wide weekly spreadsheet layout."""

    def parse_all(self, grid: ScheduleGrid) -> List[Lecture]:
        return parse_all_schedule_grid(grid)

    def parse(
        self,
        grid: ScheduleGrid,
        target_date: Optional[datetime] = None,
        fetch_full_week: bool = False,
    ) -> ParsedSchedule:
        return parse_schedule_grid(grid, target_date=target_date, fetch_full_week=fetch_full_week)
