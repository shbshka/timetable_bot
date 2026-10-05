from datetime import datetime
from html import escape

from src.parser.models import DaySchedule, Lecture
from src.utils.messages import get_msg

_WEEKDAY_KEYS = (
	"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"
)
_MONTH_KEYS = (
	"january", "february", "march", "april", "may", "june",
	"july", "august", "september", "october", "november", "december",
)


def _format_schedule_date(value: datetime, locale: str, include_year: bool) -> str:
	weekday = get_msg(f"schedule.weekdays.{_WEEKDAY_KEYS[value.weekday()]}", locale=locale)
	month = get_msg(f"schedule.months.{_MONTH_KEYS[value.month - 1]}", locale=locale)
	date_text = f"{weekday}, {value.day:02d} {month}"
	return f"{date_text} {value.year}" if include_year else date_text


def _format_lecture(lecture: Lecture, locale: str) -> str:
	time = escape(lecture.time or get_msg("schedule.time_tbd", locale=locale))
	room_info = f" (Rm {escape(lecture.room)})" if lecture.room else ""
	teacher_info = f" - <i>{escape(lecture.teacher)}</i>" if lecture.teacher else ""
	details = []
	if lecture.hours is not None:
		details.append(f"{lecture.hours:g}h")
	if lecture.form:
		details.append(escape(lecture.form))
	if lecture.delivery_mode:
		details.append(escape(lecture.delivery_mode))
	detail_text = f" ({', '.join(details)})" if details else ""
	return f"- <code>{time}</code> | <b>{escape(lecture.subject)}</b>{room_info}{teacher_info}{detail_text}\n"


def format_daily_schedule(group_name: str, date: datetime, schedule: list[DaySchedule], locale: str = "ru") -> str:
	date_str = _format_schedule_date(date, locale, include_year=True)
	lectures = schedule[0].lectures if schedule else []

	if not lectures:
		return get_msg("schedule.daily", locale=locale, group_name=group_name, date_str=date_str) + get_msg("schedule.empty", locale=locale)

	text = get_msg("schedule.daily", locale=locale, group_name=group_name, date_str=date_str)
	for lecture in lectures:
		text += _format_lecture(lecture, locale)

	return text


def format_weekly_schedule(group_name: str, weekly_schedule: list[DaySchedule], locale: str = "ru") -> str:
	week_lines = []
	for day_schedule in weekly_schedule:
		day_name = _format_schedule_date(day_schedule.date, locale, include_year=False)
		week_lines.append(f"📌 <b>{escape(day_name)}</b>")
		if not day_schedule.lectures:
			week_lines.append(get_msg("schedule.empty", locale=locale))
		else:
			week_lines.extend(
				f"  {_format_lecture(lecture, locale).rstrip()}"
				for lecture in day_schedule.lectures
			)
		week_lines.append("")

	week_schedule = "\n".join(week_lines).strip()
	if not week_schedule:
		week_schedule = get_msg("schedule.empty", locale=locale)
	return get_msg(
		"schedule.weekly",
		locale=locale,
		group_name=group_name,
		week_schedule=week_schedule,
	)