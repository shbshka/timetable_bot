"""Shared academic-year calculations used by timetable parsers and storage."""

from datetime import date
from typing import Optional


def academic_start_year(reference_date: Optional[date] = None) -> int:
    """Return the first calendar year of the academic year containing a date."""
    value = reference_date or date.today()
    return value.year if value.month >= 7 else value.year - 1


def enrollment_year(course_year: int, academic_year: Optional[int] = None) -> int:
    """Convert a displayed course number into the group's enrollment year."""
    start_year = academic_year if academic_year is not None else academic_start_year()
    return start_year - course_year + 1