from typing import Dict, Iterator, Optional

from config import SCHEDULE_PARSER
from src.parser.implementations.awful_uni_grid import AwfulUniGridParser
from src.parser.implementations.four_week_grid import FourWeekGridParser
from src.parser.interface import ScheduleParser
from src.parser.models import Lecture
from src.utils.logger import get_logger

logger = get_logger("parser")

_PARSERS: Dict[str, ScheduleParser] = {
    "four_week_grid": FourWeekGridParser(),
    "awful_uni_grid": AwfulUniGridParser(),
}
_FALLBACK_PARSER_NAME = "awful_uni_grid"


def register_parser(name: str, parser: ScheduleParser, *, replace: bool = False) -> None:
    """Register a parser implementation under a stable configuration name."""
    normalized_name = name.strip().lower()
    if not normalized_name:
        raise ValueError("Parser name must not be empty")
    if normalized_name in _PARSERS and not replace:
        raise ValueError(f"A parser named '{normalized_name}' is already registered")
    _PARSERS[normalized_name] = parser


def iter_parser_chain() -> Iterator[tuple[str, ScheduleParser]]:
    """Yield registered parsers in detection order, with the legacy parser last."""
    for name, parser in _PARSERS.items():
        if name != _FALLBACK_PARSER_NAME:
            yield name, parser
    if _FALLBACK_PARSER_NAME in _PARSERS:
        yield _FALLBACK_PARSER_NAME, _PARSERS[_FALLBACK_PARSER_NAME]


def parse_with_first_successful_parser(grid) -> tuple[str, ScheduleParser, list[Lecture]]:
    """Parse a grid with the first parser that produces at least one lecture."""
    failures = []
    for name, parser in iter_parser_chain():
        logger.debug("Trying schedule parser '%s'.", name)
        try:
            lectures = parser.parse_all(grid)
        except Exception as exc:
            failures.append(f"{name}: {exc}")
            continue
        if lectures:
            logger.info("Schedule parser '%s' produced %d lectures.", name, len(lectures))
            return name, parser, lectures
        failures.append(f"{name}: empty timetable")

    details = "; ".join(failures) or "no parsers registered"
    raise ValueError(f"No schedule parser could parse the timetable: {details}")


def get_parser(name: Optional[str] = None) -> ScheduleParser:
    """Return the configured parser, or a named parser for explicit selection."""
    parser_name = (name or SCHEDULE_PARSER).strip().lower()
    try:
        return _PARSERS[parser_name]
    except KeyError as exc:
        available = ", ".join(sorted(_PARSERS))
        raise ValueError(
            f"Unknown schedule parser '{parser_name}'. Available parsers: {available}"
        ) from exc


def available_parsers() -> tuple[str, ...]:
    return tuple(sorted(_PARSERS))
