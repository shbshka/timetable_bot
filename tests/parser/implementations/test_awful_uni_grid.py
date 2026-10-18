from datetime import date, datetime
import pytest

from src.parser.implementations import awful_uni_grid as parser


def row(values):
    return [{"value": str(value), "note": ""} for value in values]


@pytest.fixture
def grid(monkeypatch):
    monkeypatch.setattr(parser, "academic_start_year", lambda: 2026)
    result = [
        row([""] * 11 + ["W1", "", "", "", "", "", ""]),
        row([""] * 11 + [28, 29, 30, 31, 1, 2, 3]),
        row([""] * 11 + ["Dec/Jan", "", "", "", "", "", ""]),
        row([2, "Math", "lecture", "HR", "online", "course note"] + [""] * 5 + [6]),
    ]
    result[3][11]["note"] = "9:00-10:30"
    return result


def test_parser_rolls_year_and_splits_academic_hours_with_breaks(grid):
    lectures = parser.AwfulUniGridParser().parse_all(grid)
    assert len(lectures) == 3
    assert [lecture.time for lecture in lectures] == ["09:00", "10:40", "12:20"]
    assert all(lecture.date == date(2026, 12, 28) for lecture in lectures)
    assert all(lecture.hours == 2 and lecture.course_year == 2 for lecture in lectures)
    assert all(lecture.level == "HR" and lecture.delivery_mode == "online" for lecture in lectures)
    assert all(lecture.course_notes == "course note" for lecture in lectures)
    assert parser._date_columns(grid)[15] == date(2027, 1, 1)


def test_continuation_inherits_subject_but_new_section_clears_it(grid):
    grid.append(row([""] * 11 + [2]))
    grid.append(row(["3 course"]))
    grid.append(row([""] * 11 + [2]))
    lectures = parser.parse_all_schedule_grid(grid)
    assert len(lectures) == 4
    assert lectures[-1].subject == "Math"
    assert lectures[-1].course_year == 2
    assert lectures[-1].time is None


def test_week_selection_contains_seven_days_including_empty_days(grid):
    days = parser.parse_schedule_grid(grid, datetime(2027, 1, 1), fetch_full_week=True)
    assert [day.date for day in days] == [
        date(2026, 12, 28),
        date(2026, 12, 29),
        date(2026, 12, 30),
        date(2026, 12, 31),
        date(2027, 1, 1),
        date(2027, 1, 2),
        date(2027, 1, 3),
    ]
    assert len(days[0].lectures) == 3
    assert all(day.lectures == [] for day in days[1:])


@pytest.mark.parametrize("value", ["", "0", "-2", "cancelled"])
def test_non_session_cells_do_not_create_lectures(grid, value):
    grid[3][11]["value"] = value
    assert parser.parse_all_schedule_grid(grid) == []


def test_decimal_comma_hours_and_missing_notes(grid):
    grid[3][11].update(value="4,0", note="")
    lectures = parser.parse_all_schedule_grid(grid)
    assert len(lectures) == 2
    assert all(lecture.time is None and lecture.cell_note is None for lecture in lectures)


@pytest.mark.parametrize("grid", [[], [[]], [[], [], []]])
def test_empty_or_incomplete_grid_returns_no_schedule(grid):
    assert parser.AwfulUniGridParser().parse_all(grid) == []
    assert parser.AwfulUniGridParser().parse(grid) == []