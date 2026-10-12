import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.bot.jobs.notifications.dispatcher import NotificationDispatcher
from src.bot.jobs.notifications.planner import Planner
from src.db import repository


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
    monkeypatch.setattr(planner, "_now", lambda: now)
    planner.plan_notifications_for_week()

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
