from datetime import datetime
from typing import Protocol

from src.parser.models import DaySchedule, Lecture

ScheduleGrid = list[list[dict[str, str]]]
ParsedSchedule = list[DaySchedule]


class ScheduleParser(Protocol):
    """Contract implemented by each supported timetable format parser."""

    def parse_all(self, grid: ScheduleGrid) -> list[Lecture]: ...

    def parse(
        self,
        grid: ScheduleGrid,
        target_date: datetime | None = None,
        fetch_full_week: bool = False,
    ) -> ParsedSchedule: ...
