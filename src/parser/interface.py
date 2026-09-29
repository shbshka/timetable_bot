from datetime import datetime
from typing import Dict, List, Optional, Protocol

from src.parser.models import DaySchedule, Lecture

ScheduleGrid = List[List[Dict[str, str]]]
ParsedSchedule = List[DaySchedule]


class ScheduleParser(Protocol):
    """Contract implemented by each supported timetable format parser."""

    def parse_all(self, grid: ScheduleGrid) -> List[Lecture]: ...

    def parse(
        self,
        grid: ScheduleGrid,
        target_date: Optional[datetime] = None,
        fetch_full_week: bool = False,
    ) -> ParsedSchedule: ...
