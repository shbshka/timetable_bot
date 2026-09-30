from src.parser.implementations.four_week_grid import FourWeekGridParser


def _row(values: list[str]) -> list[dict[str, str]]:
    return [{"value": value, "note": ""} for value in values]


def test_four_week_layout_propagates_dates_and_reads_repeated_blocks() -> None:
    # Arrange
    grid = [
        _row(["EGU. 2026/2027. autumn semester", "", "", "", "", "", "", ""]),
        _row(["Course 2", "", "", "", "", "W01", "", "Course 2"]),
        _row(["Program Informatics", "", "", "", "", "", "", ""]),
        _row(["", "", "", "", "", "", "", ""]),
        _row(["Date", "Time", "Room", "Course", "Teacher", "Form", "", "Date", "Time", "Room", "Course", "Teacher", "Form"]),
        _row(["05/10 Mon", "08:30-10:00", "A-101", "Algorithms", "Dr Smith", "HR", "", "12/10 Mon", "10:10-11:40", "B-202", "Databases", "Dr Jones", "HR"]),
        _row(["", "10:10-11:40", "A-101", "Networks", "Dr Smith", "HR", "", "", "11:50-13:20", "B-202", "Security", "Dr Jones", "HR"]),
    ]

    # Act
    lectures = FourWeekGridParser().parse_all(grid)

    # Assert
    assert len(lectures) == 4
    assert lectures[0].date.isoformat() == "2026-10-05"
    assert lectures[1].date.isoformat() == "2026-10-05"
    assert lectures[0].course_year == 2
    assert lectures[0].level == "HR"
    assert lectures[0].hours == 1.5