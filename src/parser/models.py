from dataclasses import dataclass
from datetime import date


@dataclass
class Lecture:
    date: date
    time: str | None
    subject: str
    room: str | None = None
    teacher: str | None = None
    form: str | None = None
    hours: float | None = None
    course_year: int | None = None
    level: str | None = None
    delivery_mode: str | None = None
    course_notes: str | None = None
    cell_note: str | None = None


@dataclass
class DaySchedule:
    date: date
    lectures: list[Lecture]