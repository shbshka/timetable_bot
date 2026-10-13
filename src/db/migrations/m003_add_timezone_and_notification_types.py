import sqlite3

from src.db.migrations.base import Migration

NOTIFICATION_TYPES = (
    (1, "schedule_change"),
    (2, "day_summary"),
    (3, "reminder"),
)


class AddTimezoneAndNotificationTypesMigration(Migration):
    @property
    def version(self) -> int:
        return 3

    @property
    def name(self) -> str:
        return "add_timezone_and_notification_types"

    def upgrade(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE notification_types (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE CHECK (name <> '')
            )
            """
        )
        conn.executemany(
            "INSERT INTO notification_types (id, name) VALUES (?, ?)",
            NOTIFICATION_TYPES,
        )

        conn.execute(
            """
            ALTER TABLE users ADD COLUMN timezone TEXT NOT NULL DEFAULT 'Europe/Vilnius'
            CHECK (
                timezone GLOB '[A-Za-z]*/*'
                AND timezone NOT GLOB '*[^A-Za-z0-9_+./-]*'
                AND timezone NOT GLOB '/*'
                AND timezone NOT GLOB '*/'
                AND timezone NOT GLOB '*//*'
            )
            """
        )

        self._replace_notification_preferences(conn, use_type_ids=True)

    def downgrade(self, conn: sqlite3.Connection) -> None:
        self._replace_notification_preferences(conn, use_type_ids=False)

        conn.execute("ALTER TABLE users RENAME TO users_with_timezone")
        conn.execute(
            """
            CREATE TABLE users (
                chat_id INTEGER PRIMARY KEY,
                group_id INTEGER REFERENCES groups(id) ON DELETE SET NULL,
                username TEXT,
                name TEXT,
                locale TEXT NOT NULL DEFAULT 'ru'
                    CHECK (locale IN ('ru', 'en')),
                is_banned INTEGER NOT NULL DEFAULT 0
                    CHECK (is_banned IN (0, 1)),
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT INTO users (
                chat_id, group_id, username, name, locale, is_banned, created_at
            )
            SELECT chat_id, group_id, username, name, locale, is_banned, created_at
            FROM users_with_timezone
            """
        )
        conn.execute("DROP TABLE users_with_timezone")
        conn.execute("DROP TABLE notification_types")

    @staticmethod
    def _replace_notification_preferences(
        conn: sqlite3.Connection,
        *,
        use_type_ids: bool,
    ) -> None:
        conn.execute("ALTER TABLE notifications_queue RENAME TO notifications_queue_old")
        conn.execute(
            "ALTER TABLE notification_preferences RENAME TO notification_preferences_old"
        )

        if use_type_ids:
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
                INSERT INTO notification_preferences (
                    id, notification_type_id, recipient_id, is_enabled
                )
                SELECT p.id, t.id, p.recipient_id, p.is_enabled
                FROM notification_preferences_old p
                JOIN notification_types t ON t.name = p.type
                """
            )
        else:
            conn.execute(
                """
                CREATE TABLE notification_preferences (
                    id INTEGER PRIMARY KEY,
                    type TEXT NOT NULL CHECK (type <> ''),
                    recipient_id INTEGER NOT NULL
                        REFERENCES users(chat_id) ON DELETE CASCADE,
                    is_enabled INTEGER NOT NULL DEFAULT 1
                        CHECK (is_enabled IN (0, 1)),
                    UNIQUE(recipient_id, type)
                )
                """
            )
            conn.execute(
                """
                INSERT INTO notification_preferences (
                    id, type, recipient_id, is_enabled
                )
                SELECT p.id, t.name, p.recipient_id, p.is_enabled
                FROM notification_preferences_old p
                JOIN notification_types t ON t.id = p.notification_type_id
                """
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
            SELECT q.id, q.notification_id, q.scheduled_for,
                   q.status_id, q.status_updated_at
            FROM notifications_queue_old q
            JOIN notification_preferences p ON p.id = q.notification_id
            """
        )
        conn.execute("DROP TABLE notifications_queue_old")
        conn.execute("DROP TABLE notification_preferences_old")
