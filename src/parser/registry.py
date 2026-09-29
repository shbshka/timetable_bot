from typing import Dict, Optional

from config import SCHEDULE_PARSER
from src.parser.implementations.awful_uni_grid import AwfulUniGridParser
from src.parser.interface import ScheduleParser

_PARSERS: Dict[str, ScheduleParser] = {
    "awful_uni_grid": AwfulUniGridParser(),
}


def register_parser(name: str, parser: ScheduleParser, *, replace: bool = False) -> None:
    """Register a parser implementation under a stable configuration name."""
    normalized_name = name.strip().lower()
    if not normalized_name:
        raise ValueError("Parser name must not be empty")
    if normalized_name in _PARSERS and not replace:
        raise ValueError(f"A parser named '{normalized_name}' is already registered")
    _PARSERS[normalized_name] = parser


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
