import sqlite3

from src.db.migrations.base import Migration

NOTIFICATION_STATUSES = (
    (1, "pending"),
    (2, "processing"),
    (3, "delivered"),
    (4, "cancelled"),
    (5, "expired"),
    (6, "failed"),
)


class ExpandNotificationQueueMigration(Migration):
    @property
    def version(self) -> int:
        return 4

    @property
    def name(self) -> str:
        return "expand_notification_queue"

    def upgrade(self, conn: sqlite3.Connection) -> None:
        conn.execute("ALTER TABLE notifications_queue RENAME TO notifications_queue_old")
        conn.execute(
            "ALTER TABLE notification_preferences RENAME TO notification_preferences_old"
        )
        conn.execute("ALTER TABLE notification_types RENAME TO notification_types_old")
        conn.execute("ALTER TABLE notification_status RENAME TO notification_status_old")

        conn.execute(
            """
            CREATE TABLE notification_types (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE
                    CHECK (name IN ('schedule_change', 'day_summary', 'reminder'))
            )
            """
        )
        conn.executemany(
            "INSERT INTO notification_types (id, name) VALUES (?, ?)",
            ((1, "schedule_change"), (2, "day_summary"), (3, "reminder")),
        )
        conn.execute(
            """
            CREATE TABLE notification_preferences (
                id INTEGER PRIMARY KEY,
                notification_type_id INTEGER NOT NULL
                    REFERENCES notification_types(id) ON DELETE CASCADE,
                recipient_id INTEGER NOT NULL
                    REFERENCES users(chat_id) ON DELETE CASCADE,
                is_enabled INTEGER NOT NULL DEFAULT 0
                    CHECK (is_enabled IN (0, 1)),
                daily_time_local TEXT,
                reminder_minutes_before INTEGER,
                send_empty_schedule INTEGER NOT NULL DEFAULT 0
                    CHECK (send_empty_schedule IN (0, 1)),
                CHECK (
                    daily_time_local IS NULL OR (
                        length(daily_time_local) = 5
                        AND daily_time_local GLOB '[0-2][0-9]:[0-5][0-9]'
                        AND daily_time_local <= '23:59'
                    )
                ),
                CHECK (
                    reminder_minutes_before IS NULL
                    OR reminder_minutes_before BETWEEN 0 AND 1440
                ),
                UNIQUE(recipient_id, notification_type_id)
            )
            """
        )
        conn.execute(
            """
            INSERT INTO notification_preferences (
                id, notification_type_id, recipient_id, is_enabled
            )
            SELECT p.id, p.notification_type_id, p.recipient_id, p.is_enabled
            FROM notification_preferences_old p
            JOIN notification_types t ON t.id = p.notification_type_id
            """
        )

        conn.execute(
            """
            CREATE TABLE notification_status (
                id INTEGER PRIMARY KEY,
                status TEXT NOT NULL UNIQUE
                    CHECK (status IN (
                        'pending', 'processing', 'delivered',
                        'cancelled', 'expired', 'failed'
                    ))
            )
            """
        )
        conn.executemany(
            "INSERT INTO notification_status (id, status) VALUES (?, ?)",
            NOTIFICATION_STATUSES,
        )

        conn.execute(
            """
            CREATE TABLE notifications_queue (
                id INTEGER PRIMARY KEY,
                notification_id INTEGER NOT NULL
                    REFERENCES notification_preferences(id) ON DELETE CASCADE,
                occurrence_key TEXT NOT NULL CHECK (occurrence_key <> ''),
                scheduled_for INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                group_id INTEGER NOT NULL,
                target_date TEXT NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}',
                status_id INTEGER NOT NULL
                    REFERENCES notification_status(id) ON DELETE RESTRICT,
                attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
                next_attempt_at INTEGER NOT NULL,
                last_error TEXT,
                claim_token TEXT,
                lease_until INTEGER,
                created_at INTEGER NOT NULL,
                status_updated_at INTEGER NOT NULL,
                delivered_at INTEGER,
                CHECK (expires_at > scheduled_for),
                CHECK (next_attempt_at >= scheduled_for),
                CHECK (
                    (claim_token IS NULL AND lease_until IS NULL)
                    OR (claim_token IS NOT NULL AND lease_until IS NOT NULL)
                ),
                UNIQUE(notification_id, occurrence_key)
            )
            """
        )
        conn.execute(
            """
            INSERT INTO notifications_queue (
                id, notification_id, occurrence_key, scheduled_for, expires_at,
                group_id, target_date, payload_json, status_id, next_attempt_at,
                created_at, status_updated_at, delivered_at
            )
            SELECT
                q.id,
                p_new.id,
                COALESCE(
                    CASE
                        WHEN t_old.name LIKE 'schedule_change:%'
                        THEN t_old.name || ':' || q.id
                        ELSE t_old.name || ':' || q.id
                    END,
                    'legacy:' || q.id
                ),
                CAST(strftime('%s', q.scheduled_for) AS INTEGER),
                CAST(strftime('%s', q.scheduled_for) AS INTEGER) + 86400,
                COALESCE(u.group_id, 0),
                date(q.scheduled_for),
                '{}',
                CASE WHEN q.status_id = 2 THEN 3 ELSE 1 END,
                CAST(strftime('%s', q.scheduled_for) AS INTEGER),
                CAST(strftime('%s', q.status_updated_at) AS INTEGER),
                CAST(strftime('%s', q.status_updated_at) AS INTEGER),
                CASE
                    WHEN q.status_id = 2
                    THEN CAST(strftime('%s', q.status_updated_at) AS INTEGER)
                END
            FROM notifications_queue_old q
            JOIN notification_preferences_old p_old
              ON p_old.id = q.notification_id
            JOIN notification_types_old t_old
              ON t_old.id = p_old.notification_type_id
            JOIN users u ON u.chat_id = p_old.recipient_id
            JOIN notification_preferences p_new
              ON p_new.recipient_id = p_old.recipient_id
             AND p_new.notification_type_id = (
                 SELECT id
                 FROM notification_types
                 WHERE name = CASE
                     WHEN t_old.name LIKE 'schedule_change:%'
                     THEN 'schedule_change'
                     ELSE t_old.name
                 END
             )
            WHERE q.scheduled_for IS NOT NULL
              AND q.status_updated_at IS NOT NULL
            """
        )
        conn.execute(
            "CREATE INDEX idx_notifications_queue_status_next "
            "ON notifications_queue(status_id, next_attempt_at)"
        )
        conn.execute(
            "CREATE INDEX idx_notifications_queue_status_lease "
            "ON notifications_queue(status_id, lease_until)"
        )
        for table in (
            "notifications_queue_old",
            "notification_preferences_old",
            "notification_types_old",
            "notification_status_old",
        ):
            conn.execute(f'DROP TABLE "{table}"')

    def downgrade(self, conn: sqlite3.Connection) -> None:
        conn.execute("ALTER TABLE notifications_queue RENAME TO notifications_queue_new")
        conn.execute(
            "ALTER TABLE notification_preferences RENAME TO notification_preferences_new"
        )
        conn.execute("ALTER TABLE notification_status RENAME TO notification_status_new")
        conn.execute("ALTER TABLE notification_types RENAME TO notification_types_new")
        conn.execute(
            """
            CREATE TABLE notification_types (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE CHECK (name <> '')
            )
            """
        )
        conn.execute(
            """
            INSERT INTO notification_types
            SELECT id, name FROM notification_types_new
            """
        )
        conn.execute(
            """
            CREATE TABLE notification_preferences (
                id INTEGER PRIMARY KEY,
                notification_type_id INTEGER NOT NULL
                    REFERENCES notification_types(id) ON DELETE CASCADE,
                recipient_id INTEGER NOT NULL
                    REFERENCES users(chat_id) ON DELETE CASCADE,
                is_enabled INTEGER NOT NULL DEFAULT 1
                    CHECK (is_enabled IN (0, 1)),
                UNIQUE(recipient_id, notification_type_id)
            )
            """
        )
        conn.execute(
            """
            INSERT INTO notification_preferences
            SELECT id, notification_type_id, recipient_id, is_enabled
            FROM notification_preferences_new
            """
        )
        conn.execute(
            """
            CREATE TABLE notification_status (
                id INTEGER PRIMARY KEY,
                status TEXT NOT NULL UNIQUE
            )
            """
        )
        conn.execute(
            "INSERT INTO notification_status SELECT id, status FROM notification_status_new WHERE id IN (1, 3)"
        )
        conn.execute(
            """
            CREATE TABLE notifications_queue (
                id INTEGER PRIMARY KEY,
                notification_id INTEGER NOT NULL
                    REFERENCES notification_preferences(id) ON DELETE CASCADE,
                scheduled_for TIMESTAMP NOT NULL,
                status_id INTEGER NOT NULL
                    REFERENCES notification_status(id) ON DELETE RESTRICT,
                status_updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(notification_id, scheduled_for)
            )
            """
        )
        conn.execute(
            """
            INSERT INTO notifications_queue (
                id, notification_id, scheduled_for, status_id, status_updated_at
            )
            SELECT id, notification_id, datetime(scheduled_for, 'unixepoch'),
                   CASE WHEN status_id = 3 THEN 2 ELSE 1 END,
                   datetime(status_updated_at, 'unixepoch')
            FROM notifications_queue_new
            """
        )
        for table in (
            "notifications_queue_new",
            "notification_preferences_new",
            "notification_status_new",
            "notification_types_new",
        ):
            conn.execute(f'DROP TABLE "{table}"')
