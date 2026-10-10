"""Parser for the four-week, horizontally repeated timetable export."""

import re
from datetime import date, datetime, timedelta

from config import STUDY_FORMS
from src.parser.academic_year import academic_start_year
from src.parser.interface import ParsedSchedule, ScheduleGrid
from src.parser.models import DaySchedule, Lecture
from src.utils.time import institution_today
from src.utils.logger import get_logger

_DATE_RE = re.compile(r"(?<!\d)(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?")
_TIME_RE = re.compile(r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)")
_COURSE_YEAR_RE = re.compile(r"\b(?:курс|course)\s*(\d+)\b", re.IGNORECASE)
logger = get_logger("parser")


def _value(grid: ScheduleGrid, row: int, column: int) -> str:
    if row < 0 or row >= len(grid) or column < 0 or column >= len(grid[row]):
        return ""
    cell = grid[row][column]
    if cell is None:
        return ""
    if not isinstance(cell, dict):
        return str(cell).strip()
    val = cell.get("value")
    if val is None:
        return ""
    return str(val).strip()


def _note(grid: ScheduleGrid, row: int, column: int) -> str:
    if row < 0 or row >= len(grid) or column < 0 or column >= len(grid[row]):
        return ""
    cell = grid[row][column]
    if cell is None:
        return ""
    if not isinstance(cell, dict):
        return str(cell).strip()
    note = cell.get("note")
    if note is None:
        return ""
    return str(note).strip()


def _find_header_blocks(grid: ScheduleGrid) -> list[tuple[int, int]]:
    blocks = []
    for row_index, row in enumerate(grid):
        for column, cell in enumerate(row):
            val = _value(grid, row_index, column).lower()
            if val != "date":
                continue
            header = [_value(grid, row_index, column + offset).lower() for offset in range(6)]
            logger.debug(f"Found 'date' at row {row_index}, col {column}. Header slice: {header}")

            if header[1:4] == ["time", "room", "course"]:
                blocks.append((row_index, column))
            else:
                logger.debug(f"Header mismatch! Expected time/room/course at offsets 1-3, got {header[1:4]}")
    return blocks


def _course_year(grid: ScheduleGrid, header_row: int, start_column: int) -> int | None:
    for row_index in range(max(0, header_row - 4), header_row):
        text = " ".join(_value(grid, row_index, column) for column in range(start_column, start_column + 6))
        match = _COURSE_YEAR_RE.search(text)
        if match:
            return int(match.group(1))
    return None


def _parse_date(value: str, academic_year: int, previous: date | None) -> date | None:
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


def _duration_hours(value: str) -> float | None:
    matches = _TIME_RE.findall(value)
    if len(matches) < 2:
        return None
    start = int(matches[0][0]) * 60 + int(matches[0][1])
    end = int(matches[1][0]) * 60 + int(matches[1][1])
    duration = (end - start) / 60
    return duration if duration > 0 else None


def _study_form(form: str | None) -> str | None:
    if not form:
        return None
    normalized = form.strip().upper()
    return normalized if normalized in STUDY_FORMS else None


def parse_all_schedule_grid(grid: ScheduleGrid) -> list[Lecture]:
    academic_year = academic_start_year()
    lectures: list[Lecture] = []
    seen = set()

    for header_row, start_column in _find_header_blocks(grid):
        course_year = _course_year(grid, header_row, start_column)
        current_date: date | None = None
        current_time: str | None = None

        for row_index in range(header_row + 1, len(grid)):
            date_value = _value(grid, row_index, start_column)
            parsed_date = _parse_date(date_value, academic_year, current_date)
            if parsed_date:
                current_date = parsed_date

            time_value = _value(grid, row_index, start_column + 1)
            if _TIME_RE.search(time_value):
                current_time = time_value

            cell_item = grid[row_index][start_column + 3] if row_index < len(grid) and start_column + 3 < len(
                grid[row_index]) else {}
            if isinstance(cell_item, dict):
                sub_val = cell_item.get("value")
                subject = str(sub_val if sub_val is not None else "").strip()
                is_strikethrough = bool(cell_item.get("strikethrough", False))
            else:
                subject = str(cell_item if cell_item is not None else "").strip()
                is_strikethrough = False

            cell_note = _note(grid, row_index, start_column + 3)
            time = current_time or cell_note

            # Пропускаем, если нет даты, предмета, времени ИЛИ если предмет зачеркнут в таблице
            if not current_date or not subject or not time or is_strikethrough:
                continue

            group_value = _value(grid, row_index, start_column + 4) or None
            form_value = _value(grid, row_index, start_column + 5) or None

            lecture = Lecture(
                date=current_date,
                time=time,
                room=_value(grid, row_index, start_column + 2) or None,
                subject=subject,
                teacher=None,
                form=form_value,
                hours=_duration_hours(time),
                course_year=course_year,
                level=_study_form(form_value),
                course_notes=group_value,
                cell_note=cell_note or None,
            )

            unique_key = (lecture.date, lecture.time, lecture.subject, lecture.room, group_value)
            if unique_key not in seen:
                seen.add(unique_key)
                lectures.append(lecture)

    return lectures


def parse_schedule_grid(
    grid: ScheduleGrid,
    target_date: datetime | None = None,
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
        target_date: datetime | None = None,
        fetch_full_week: bool = False,
    ) -> ParsedSchedule:
        return parse_schedule_grid(grid, target_date=target_date, fetch_full_week=fetch_full_week)