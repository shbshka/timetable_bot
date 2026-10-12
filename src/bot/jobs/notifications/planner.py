from datetime import UTC, datetime, time, timedelta
from typing import ClassVar
from zoneinfo import ZoneInfo

from config import INSTITUTION_TIMEZONE

from src.db import repository
from src.db.db_repository.notification_status_repository import NotificationStatusRepository
from src.db.db_repository.notifications_queue_repository import NotificationQueueRepository
from src.db.db_repository.notifications_repository import NotificationPreferencesRepository

from src.utils.logger import get_logger
from src.utils.time import resolve_local_time, utc_now

logger = get_logger("jobs")


class Planner:
    REGULAR_TYPES: ClassVar[set[str]] = {"day_summary", "reminder"}

    def __init__(
        self,
        *,
        institution_timezone: ZoneInfo = INSTITUTION_TIMEZONE,
        horizon_days: int = 7,
        retention_days: int = 30,
    ):
        if horizon_days < 1 or retention_days < 1:
            raise ValueError("Planning and retention days must be positive")

        self.notifications_repository = NotificationPreferencesRepository()
        self.notification_status_repository = NotificationStatusRepository()
        self.notification_queue_repository = NotificationQueueRepository()

        self.institution_timezone = ZoneInfo(institution_timezone)
        self.horizon_days = horizon_days
        self.retention_days = retention_days


    def _scheduling_horizon(self, now: datetime) -> list[datetime.date]:
        """
        Converts the current time to the institution's timezone and generates a list of dates
        from today to the end of the planning horizon.

        returns: a list of dates from today to the end of the planning horizon
        """
        first = now.astimezone(self.institution_timezone).date()
        return [
            first + timedelta(days=offset)
            for offset in range(self.horizon_days)
        ] 


    def _get_lectures_for_scheduling_horizon(self, conn, group_id: int, dates) -> list[dict]:
        """
        Fetches lectures for a specific group within the scheduling horizon.
        returns: a list of dictionaries representing the lectures
        """
        rows = conn.execute(
            """
            SELECT id, source_id, lecture_date, lecture_time,
                   subject, room, teacher
            FROM lectures
            WHERE group_id = ?
              AND lecture_date >= ?
              AND lecture_date <= ?
            ORDER BY lecture_date, lecture_time, id
            """,
            (group_id, dates[0].isoformat(), dates[-1].isoformat()),
        ).fetchall()

        return [dict(row) for row in rows]


    def _daily_summary_occurrences(
        self, preference: dict, lectures: list[dict], dates, now: datetime,
    ) -> list[dict]:
        """
        Generates daily summary occurrences for a given preference and lectures.

        returns: a list of dictionaries representing the daily summary occurrences
        """

        if preference["daily_time_local"] is None:
            raise ValueError(f"Local daily time missing for preference {preference['id']}.")

        delivery_time = time.fromisoformat(preference["daily_time_local"])
        lecture_dates = {row["lecture_date"] for row in lectures}
        result = []
        now_seconds = int(now.timestamp())

        for target_date in dates:
            if (
                not preference["send_empty_schedule"]
                and target_date.isoformat() not in lecture_dates
            ):
                continue

            local = resolve_local_time(
                datetime.combine(target_date, delivery_time),
                preference["timezone"],
            )
            due = int(local.timestamp())

            if due <= now_seconds:
                continue

            result.append({
                "occurrence_key": (
                    f"daily:{preference['group_id']}:{target_date.isoformat()}"
                ),
                "scheduled_for": due,
                "expires_at": due + 2 * 3600,
                "group_id": preference["group_id"],
                "target_date": target_date.isoformat(),
                "payload": {},
            })

        return result


    def _reminder_occurrences(
        self, preference: dict, lectures: list[dict], now: datetime,
    ) -> list[dict]:
        """
        Generates reminder occurrences for a given preference and lectures.
        Checks for valid reminder lead times, 
        handles lectures without a specified time,
        covers DST repeated hour & skipped hour scenarios,
        ensures reminders are not scheduled in the past.
        
        returns: a list of dictionaries representing the reminder occurrences
        """

        minutes = preference["reminder_minutes_before"]
        if minutes is None or not 0 <= minutes <= 1440:
            raise ValueError(f"Invalid reminder lead time for preference {preference['id']}")

        result = []
        now_seconds = int(now.timestamp())

        for lecture in lectures:
            if not lecture["lecture_time"]:
                continue

            naive = datetime.combine(
                datetime.fromisoformat(lecture["lecture_date"]).date(),
                time.fromisoformat(lecture["lecture_time"]),
            )
            local = naive.replace(tzinfo=self.institution_timezone)
            alternative = local.replace(fold=1)

            roundtrip = local.astimezone(UTC).astimezone(self.institution_timezone)

            # I mean, I have no idea why this should happen, 
            # but let's be safe if somebody genious messes up AM and PM in the google sheet
            # (I hate timezones)
            if (
                roundtrip.replace(tzinfo=None) != naive
                or local.utcoffset() != alternative.utcoffset()
            ):
                raise ValueError(f"Lecture {lecture['id']} has an invalid or ambiguous time")

            start_at = int(local.astimezone(UTC).timestamp())
            due = start_at - minutes * 60

            if due <= now_seconds:
                continue

            result.append({
                "occurrence_key": (
                    f"reminder:{preference['group_id']}:{lecture['id']}"
                ),
                "scheduled_for": due,
                "expires_at": start_at if minutes else start_at + 60,
                "group_id": preference["group_id"],
                "target_date": lecture["lecture_date"],
                "payload": {
                    "lecture_id": lecture["id"],
                    "source_id": lecture["source_id"],
                    "lecture_start_at": start_at,
                    "subject": lecture["subject"],
                    "room": lecture["room"],
                    "teacher": lecture["teacher"],
                },
            })

        return result


    def _plan_preference(
            self, 
            conn, 
            preference: dict, 
            statuses: dict, 
            now: datetime, 
            *, 
            replan: bool) -> None:
        """
        Plans notifications for a specific user preference withing the scheduling horizon,
        cancelling disabled, nonexistent, or banned preferences.
        """
        
        now_seconds = int(now.timestamp())

        if (
            not preference["is_enabled"]
            or preference["is_banned"]
            or preference["group_id"] is None
        ):
            self.notification_queue_repository.cancel_pending(conn, preference["id"], statuses, now_seconds)
            return

        notification_type = preference["notification_type"]
        if notification_type == "schedule_change":
            return

        if notification_type not in self.REGULAR_TYPES:
            raise ValueError(
                f"Unsupported notification type: {notification_type}"
            )

        dates = self._scheduling_horizon(now)
        lectures = self._get_lectures_for_scheduling_horizon(conn, preference["group_id"], dates)

        if notification_type == "day_summary":
            desired = self._daily_summary_occurrences(preference, lectures, dates, now)          
        elif notification_type == "reminder":
            desired = self._reminder_occurrences(preference, lectures, now)

        if not replan:
            existing_due = conn.execute(
                """
                SELECT *
                FROM notifications_queue
                WHERE notification_id = ?
                  AND status_id = ?
                  AND scheduled_for <= ?
                  AND expires_at > ?
                """,
                (
                    preference["id"], statuses["pending"],
                    now_seconds, now_seconds,
                ),
            ).fetchall()

            import json

            for row in existing_due:
                desired.append({
                    "occurrence_key": row["occurrence_key"],
                    "scheduled_for": row["scheduled_for"],
                    "expires_at": row["expires_at"],
                    "group_id": row["group_id"],
                    "target_date": row["target_date"],
                    "payload": json.loads(row["payload_json"]),
                })

        self.notification_queue_repository.reconcile(
            conn,
            preference_id=preference["id"],
            occurrences=desired,
            statuses=statuses,
            now=now_seconds,
        )

    
    def cleanup_old_notifications(self) -> int:
        """
        Cleans up old notifications from the queue.
        
        returns: the count of deleted records
        """
        now = utc_now()

        now_seconds = int(now.timestamp())
        cutoff = int(
            (now - timedelta(days=self.retention_days)).timestamp()
        )

        with repository.get_db_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                statuses = self.notification_status_repository.get_status_ids(conn)

                self.notification_queue_repository \
                    .expire_pending(conn, statuses, now_seconds)
                
                deleted = self.notification_queue_repository \
                    .delete_old_terminal(conn, statuses, cutoff)
                
                conn.commit()
                return deleted
            except Exception:
                conn.rollback()
                logger.exception("Failed to cleanup old notifications")
                raise


    def _plan_notifications_for_week(
        self,
        *,
        user_id: int | None = None,
        notification_type: str | None = None,
        replan: bool = False,
    ) -> None:
        """
        Plans notifications for the upcoming week for all users or a specific user.
        If user_id is provided, only that user's preferences are planned.
        """
        now = utc_now()

        with repository.get_db_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                statuses = self.notification_status_repository.get_status_ids(conn)
                self.notification_queue_repository.expire_pending(conn, statuses, int(now.timestamp()))

                preferences = self.notifications_repository.get_planning_preferences(conn, user_id)

                if notification_type is not None:
                    preferences = [
                        p for p in preferences
                        if p["notification_type"] == notification_type
                    ]

                for preference in preferences:
                    self._plan_preference(conn, preference, statuses, now, replan=replan)

                conn.commit()
            except Exception as e:
                conn.rollback()
                raise


    def replan_notifications_for_user(self, user_id: int) -> None:
        """
        Synchronizes notifications for a specific user after changes in their preferences or schedule.
        """
        self._plan_notifications_for_week(user_id=user_id, replan=True)


    def run_planner(self) -> None:
        """
        Runs the notification planner for all users,
        cleans up old notifications.
        """
        self._plan_notifications_for_week()
        self.cleanup_old_notifications()