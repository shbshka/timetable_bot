import asyncio
import json
from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest

from src.bot.jobs.notifications.dispatcher import NotificationDispatcher
from src.bot.jobs.notifications.planner import Planner
from src.db import repository
from src.utils.messages import get_msg


def _notification_preference(user_id: int, notification_type: str) -> int:
    with repository.get_db_connection() as conn:
        return conn.execute(
            """
            SELECT p.id
            FROM notification_preferences p
            JOIN notification_types t ON t.id = p.notification_type_id
            WHERE p.recipient_id = ? AND t.name = ?
            """,
            (user_id, notification_type),
        ).fetchone()["id"]


def test_planner_uses_the_recipient_timezone(initialized_test_database, monkeypatch) -> None:
    repository.register_user_if_not_exists(42)
    group = repository.get_group_by_form_and_year("HR", 2025)
    repository.set_user_group(42, group["id"])

    with repository.get_db_connection() as conn:
        conn.execute(
            """
            UPDATE notification_preferences
            SET is_enabled = 1, daily_time_local = '09:00',
                send_empty_schedule = 1
            WHERE id = ?
            """,
            (_notification_preference(42, "day_summary"),),
        )

    now = datetime(2026, 10, 10, 10, tzinfo=UTC)
    planner = Planner(horizon_days=2)
    monkeypatch.setattr(
        "src.bot.jobs.notifications.planner.utc_now",
        lambda: now,
    )
    planner._plan_notifications_for_week()

    with repository.get_db_connection() as conn:
        row = conn.execute(
            """
            SELECT q.scheduled_for, q.target_date
            FROM notifications_queue q
            WHERE q.notification_id = ?
            """,
            (_notification_preference(42, "day_summary"),),
        ).fetchone()

    assert row["target_date"] == "2026-10-11"
    assert row["scheduled_for"] == int(
        datetime(2026, 10, 11, 6, tzinfo=UTC).timestamp()
    )


def test_planner_skips_empty_days_and_past_daily_summaries() -> None:
    planner = Planner(horizon_days=2)
    preference = {
        "id": 1,
        "daily_time_local": "09:00",
        "send_empty_schedule": 0,
        "group_id": 7,
        "timezone": "Europe/Vilnius",
    }
    now = datetime(2026, 10, 10, 10, tzinfo=UTC)
    lectures = [{"lecture_date": "2026-10-11"}]

    occurrences = planner._daily_summary_occurrences(
        preference,
        lectures,
        [date(2026, 10, 10), date(2026, 10, 11)],
        now,
    )

    assert occurrences == [{
        "occurrence_key": "daily:7:2026-10-11",
        "scheduled_for": int(datetime(2026, 10, 11, 6, tzinfo=UTC).timestamp()),
        "expires_at": int(datetime(2026, 10, 11, 8, tzinfo=UTC).timestamp()),
        "group_id": 7,
        "target_date": "2026-10-11",
        "payload": {},
    }]


def test_planner_defaults_invalid_reminder_and_skips_untimed_lecture() -> None:
    planner = Planner(institution_timezone=ZoneInfo("Europe/Vilnius"))
    preference = {
        "id": 1,
        "reminder_minutes_before": None,
        "group_id": 7,
    }
    lectures = [
        {
            "id": 11,
            "source_id": "source-11",
            "lecture_date": "2026-10-12",
            "lecture_time": "12:00",
            "subject": "Math",
            "room": None,
            "teacher": "Teacher",
        },
        {
            "id": 12,
            "source_id": "source-12",
            "lecture_date": "2026-10-12",
            "lecture_time": None,
            "subject": "Untimed",
            "room": None,
            "teacher": None,
        },
    ]

    occurrences = planner._reminder_occurrences(
        preference,
        lectures,
        datetime(2026, 10, 10, 10, tzinfo=UTC),
    )

    assert len(occurrences) == 1
    assert occurrences[0]["occurrence_key"] == "reminder:7:11"
    assert occurrences[0]["payload"]["subject"] == "Math"
    assert occurrences[0]["expires_at"] == occurrences[0]["payload"]["lecture_start_at"]


def test_planner_rejects_ambiguous_reminder_time() -> None:
    planner = Planner(institution_timezone=ZoneInfo("Europe/Vilnius"))
    preference = {"id": 1, "reminder_minutes_before": 0, "group_id": 7}
    lecture = {
        "id": 11,
        "source_id": "source-11",
        "lecture_date": "2026-10-25",
        "lecture_time": "03:30",
        "subject": "Math",
        "room": "101",
        "teacher": "Teacher",
    }

    with pytest.raises(ValueError, match="invalid or ambiguous"):
        planner._reminder_occurrences(
            preference,
            [lecture],
            datetime(2026, 10, 10, 10, tzinfo=UTC),
        )


def test_dispatcher_renders_reminder_with_timezone_and_tbd_room() -> None:
    dispatcher = NotificationDispatcher()
    start_at = int(datetime(2026, 10, 12, 9, tzinfo=UTC).timestamp())
    notification = {
        "notification_type": "reminder",
        "locale": "en",
        "group_name": "HR",
        "group_id": 7,
        "target_date": "2026-10-12",
        "timezone": "Europe/Vilnius",
        "payload_json": json.dumps({
            "lecture_start_at": start_at,
            "subject": "Math",
            "room": None,
        }),
    }

    rendered = dispatcher._render(notification)

    assert "Math" in rendered
    assert "12:00" in rendered
    assert get_msg("schedule.time_tbd", locale="en") in rendered


def test_dispatcher_rejects_unknown_notification_type() -> None:
    notification = {
        "notification_type": "unknown",
        "locale": "en",
        "group_name": "HR",
        "group_id": 7,
        "target_date": "2026-10-12",
    }

    with pytest.raises(ValueError, match="Unsupported notification type"):
        NotificationDispatcher()._render(notification)


def test_dispatcher_returns_zero_when_no_notifications_are_due(initialized_test_database) -> None:
    sender = AsyncMock()

    delivered = asyncio.run(
        NotificationDispatcher(clock=lambda: 150).dispatch(
            SimpleNamespace(send_message=sender)
        )
    )

    assert delivered == 0
    sender.assert_not_awaited()


def test_dispatcher_claims_and_marks_delivery(initialized_test_database) -> None:
    repository.register_user_if_not_exists(42)
    group = repository.get_group_by_form_and_year("HR", 2025)
    repository.set_user_group(42, group["id"])
    preference_id = _notification_preference(42, "schedule_change")

    with repository.get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO notifications_queue (
                notification_id, occurrence_key, scheduled_for, expires_at,
                group_id, target_date, payload_json, status_id, next_attempt_at,
                created_at, status_updated_at
            )
            VALUES (?, 'change:1', 100, 200, ?, '2026-10-10', '{}', 1, 100, 100, 100)
            """,
            (preference_id, group["id"]),
        )

    sender = AsyncMock()
    dispatcher = NotificationDispatcher(clock=lambda: 150)
    delivered = asyncio.run(dispatcher.dispatch(SimpleNamespace(send_message=sender)))

    assert delivered == 1
    sender.assert_awaited_once()
    with repository.get_db_connection() as conn:
        assert conn.execute(
            "SELECT status_id FROM notifications_queue WHERE occurrence_key = 'change:1'"
        ).fetchone()["status_id"] == 3


def test_dispatcher_requeues_failed_delivery(initialized_test_database) -> None:
    repository.register_user_if_not_exists(42)
    group = repository.get_group_by_form_and_year("HR", 2025)
    repository.set_user_group(42, group["id"])
    preference_id = _notification_preference(42, "schedule_change")

    with repository.get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO notifications_queue (
                notification_id, occurrence_key, scheduled_for, expires_at,
                group_id, target_date, payload_json, status_id, next_attempt_at,
                created_at, status_updated_at
            )
            VALUES (?, 'change:2', 100, 200, ?, '2026-10-10', '{}', 1, 100, 100, 100)
            """,
            (preference_id, group["id"]),
        )

    async def fail(**_kwargs):
        raise RuntimeError("telegram unavailable")

    dispatcher = NotificationDispatcher(clock=lambda: 150)
    asyncio.run(dispatcher.dispatch(SimpleNamespace(send_message=fail)))

    with repository.get_db_connection() as conn:
        row = conn.execute(
            """
            SELECT status_id, attempt_count, last_error
            FROM notifications_queue
            WHERE occurrence_key = 'change:2'
            """
        ).fetchone()
    assert row["status_id"] == 1
    assert row["attempt_count"] == 1
    assert row["last_error"] == "telegram unavailable"
