from datetime import date

import pytest

from src.parser import registry
from src.parser.models import Lecture


class EmptyParser:
    def parse_all(self, grid):
        return []

    def parse(self, grid, target_date=None, fetch_full_week=False):
        return []


class SuccessfulParser(EmptyParser):
    def parse_all(self, grid):
        return [Lecture(date=date(2026, 10, 5), time="08:30-10:00", subject="Test")]


class RaisingParser(EmptyParser):
    def parse_all(self, grid):
        raise RuntimeError("bad layout")


def test_parser_chain_selects_first_nonempty_result_and_keeps_legacy_last(monkeypatch) -> None:
    # Arrange
    monkeypatch.setattr(
        registry,
        "_PARSERS",
        {
            "empty": EmptyParser(),
            "raising": RaisingParser(),
            "successful": SuccessfulParser(),
            "awful_uni_grid": EmptyParser(),
        },
    )

    # Act
    names = [name for name, _ in registry.iter_parser_chain()]
    selected_name, _, lectures = registry.parse_with_first_successful_parser([])

    # Assert
    assert names == ["empty", "raising", "successful", "awful_uni_grid"]
    assert selected_name == "successful"
    assert len(lectures) == 1


def test_parser_chain_rejects_a_timetable_when_all_parsers_fail(monkeypatch) -> None:
    # Arrange
    monkeypatch.setattr(registry, "_PARSERS", {"awful_uni_grid": EmptyParser()})

    # Act
    result = pytest.raises(ValueError, registry.parse_with_first_successful_parser, [])

    # Assert
    assert "No schedule parser could parse" in str(result.value)