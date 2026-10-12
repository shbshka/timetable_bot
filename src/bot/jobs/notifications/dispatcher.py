import json
from datetime import UTC, date, datetime
from time import time
from zoneinfo import ZoneInfo

from telegram.ext import ContextTypes

from src.bot.jobs.notifications.planner import Planner
from src.db import repository
from src.db.db_repository.notification_status_repository import (
    NotificationStatusRepository,
)
from src.db.db_repository.notifications_queue_repository import (
    NotificationQueueRepository,
)
from src.parser.models import DaySchedule, Lecture
from src.utils.formatter import format_daily_schedule
from src.utils.logger import get_logger
from src.utils.messages import get_msg

logger = get_logger("jobs")


class NotificationDispatcher:
    """Claims and delivers queued notifications using SQLite as the source of truth."""

    def __init__(
        self,
        *,
        lease_seconds: int = 300,
        max_attempts: int = 3,
        batch_size: int = 50,
        clock=time,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("Maximum attempts must be positive")
        self.lease_seconds = lease_seconds
        self.max_attempts = max_attempts
        self.batch_size = batch_size
        self.clock = clock
        self.status_repository = NotificationStatusRepository()
        self.queue_repository = NotificationQueueRepository()

    async def dispatch(self, bot) -> int:
        """Deliver one batch of due notifications and return its size."""
        now = int(self.clock())
        with repository.get_db_connection() as conn:
            statuses = self.status_repository.get_status_ids(conn)
            notifications = self.queue_repository.claim_due(
                conn,
                statuses,
                now=now,
                lease_seconds=self.lease_seconds,
                limit=self.batch_size,
            )

        delivered = 0
        for notification in notifications:
            try:
                await bot.send_message(
                    chat_id=notification["recipient_id"],
                    text=self._render(notification),
                    parse_mode="HTML",
                )
            except Exception as error:
                logger.warning(
                    "Notification %s failed for chat %s: %s",
                    notification["id"],
                    notification["recipient_id"],
                    error,
                    exc_info=True,
                )
                with repository.get_db_connection() as conn:
                    self.queue_repository.mark_failed(
                        conn,
                        notification["id"],
                        notification["_claim_token"],
                        statuses=statuses,
                        now=int(self.clock()),
                        error=str(error),
                        max_attempts=self.max_attempts,
                    )
                continue

            with repository.get_db_connection() as conn:
                if self.queue_repository.mark_delivered(
                    conn,
                    notification["id"],
                    notification["_claim_token"],
                    status_id=statuses["delivered"],
                    processing_status_id=statuses["processing"],
                    now=int(self.clock()),
                ):
                    delivered += 1
        return delivered

    def _render(self, notification: dict) -> str:
        notification_type = notification["notification_type"]
        locale = notification["locale"]
        group_name = notification["group_name"] or str(notification["group_id"])
        target_date = notification["target_date"]

        if notification_type == "schedule_change":
            return get_msg(
                "schedule.updated",
                locale=locale,
                group_name=group_name,
                date_str=target_date,
            )

        if notification_type == "day_summary":
            lectures = self._get_lectures(
                notification["group_id"], target_date,
            )
            schedule = [
                DaySchedule(
                    date=date.fromisoformat(target_date),
                    lectures=lectures,
                )
            ]
            return format_daily_schedule(
                group_name,
                datetime.fromisoformat(target_date),
                schedule,
                locale=locale,
            )

        if notification_type == "reminder":
            payload = json.loads(notification["payload_json"])
            return get_msg(
                "notifications.reminder_message",
                locale=locale,
                subject=payload["subject"],
                time=(
                    datetime.fromtimestamp(
                        payload["lecture_start_at"], tz=UTC,
                    ).astimezone(
                        ZoneInfo(notification["timezone"]),
                    ).strftime("%H:%M")
                ),
                room=payload.get("room") or get_msg(
                    "schedule.time_tbd", locale=locale,
                ),
            )

        raise ValueError(f"Unsupported notification type: {notification_type}")

    @staticmethod
    def _get_lectures(group_id: int, target_date: str) -> list[Lecture]:
        with repository.get_db_connection() as conn:
            rows = conn.execute(
                """
                SELECT lecture_date, lecture_time, subject, room, teacher,
                       duration_academic_hours, delivery_mode
                FROM lectures
                WHERE group_id = ? AND lecture_date = ?
                ORDER BY lecture_time, id
                """,
                (group_id, target_date),
            ).fetchall()
        return [
            Lecture(
                date=date.fromisoformat(row["lecture_date"]),
                time=row["lecture_time"],
                subject=row["subject"],
                room=row["room"],
                teacher=row["teacher"],
                hours=row["duration_academic_hours"],
                delivery_mode=row["delivery_mode"],
            )
            for row in rows
        ]


def plan_notifications_job(_context: ContextTypes.DEFAULT_TYPE) -> None:
    Planner().run_planner()


async def dispatch_notifications_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    await NotificationDispatcher().dispatch(context.bot)


def create_notification_jobs(application) -> None:
    """Register planning and delivery jobs on a Telegram application."""
    if not application.job_queue:
        logger.warning("JobQueue not enabled. Notification jobs will not run.")
        return

    application.job_queue.run_repeating(
        plan_notifications_job,
        interval=300,
        first=0,
        name="notification_planner",
    )
    application.job_queue.run_repeating(
        dispatch_notifications_job,
        interval=10,
        first=1,
        name="notification_dispatcher",
    )