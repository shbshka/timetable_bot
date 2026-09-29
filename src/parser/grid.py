"""Compatibility: legacy imports -> the parser registry."""

from datetime import datetime
from typing import Optional

from src.parser.interface import ParsedSchedule, ScheduleGrid
from src.parser.registry import get_parser
from src.parser.models import Lecture


def parse_schedule_grid(
    grid: ScheduleGrid,
    target_date: Optional[datetime] = None,
    fetch_full_week: bool = False,
) -> ParsedSchedule:
    return get_parser().parse(grid, target_date=target_date, fetch_full_week=fetch_full_week)


def parse_all_schedule_grid(grid: ScheduleGrid) -> list[Lecture]:
    return get_parser().parse_all(grid)

__all__ = [
    "ParsedSchedule",
    "ScheduleGrid",
    "parse_all_schedule_grid",
    "parse_schedule_grid",
]
