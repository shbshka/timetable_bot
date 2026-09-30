from datetime import date

from src.parser.academic_year import academic_start_year, enrollment_year


def test_academic_year_uses_july_as_the_boundary() -> None:
    # Arrange
    before_boundary = date(2026, 6, 30)
    on_boundary = date(2026, 7, 1)

    # Act
    before_year = academic_start_year(before_boundary)
    on_boundary_year = academic_start_year(on_boundary)

    # Assert
    assert before_year == 2025
    assert on_boundary_year == 2026


def test_course_year_maps_to_enrollment_year() -> None:
    # Arrange
    course_year = 2
    academic_year = 2026

    # Act
    result = enrollment_year(course_year, academic_year)

    # Assert
    assert result == 2025