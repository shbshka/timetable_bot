from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class Lecture:
    date: date
    time: Optional[str]
    subject: str
    room: Optional[str] = None
    teacher: Optional[str] = None
    form: Optional[str] = None
    hours: Optional[float] = None
    course_year: Optional[int] = None
    level: Optional[str] = None
    delivery_mode: Optional[str] = None
    course_notes: Optional[str] = None
    cell_note: Optional[str] = None


@dataclass
class DaySchedule:
    date: date
    lectures: list[Lecture]