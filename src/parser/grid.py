"""Compatibility: legacy imports -> the parser registry."""

from datetime import datetime

from src.parser.interface import ParsedSchedule, ScheduleGrid
from src.parser.models import Lecture
from src.parser.registry import parse_with_first_successful_parser


def parse_schedule_grid(
    grid: ScheduleGrid,
    target_date: datetime | None = None,
    fetch_full_week: bool = False,
) -> ParsedSchedule:
    _, parser, _ = parse_with_first_successful_parser(grid)
    return parser.parse(grid, target_date=target_date, fetch_full_week=fetch_full_week)


def parse_all_schedule_grid(grid: ScheduleGrid) -> list[Lecture]:
    _, _, lectures = parse_with_first_successful_parser(grid)
    return lectures

__all__ = [
    "ParsedSchedule",
    "ScheduleGrid",
    "parse_all_schedule_grid",
    "parse_schedule_grid",
]
