import sqlite3

from src.db.migrations.base import Migration

BASELINE_TABLES = (
    """
    -- 1. Groups
    CREATE TABLE IF NOT EXISTS groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        study_form TEXT NOT NULL,
        enrollment_year INTEGER NOT NULL,

        group_name TEXT GENERATED ALWAYS AS (
            PRINTF('%02d', enrollment_year % 100) || study_form
        ) STORED,

        UNIQUE(study_form, enrollment_year)
    );
    """,
    """
    -- 2. Spreadsheets
    CREATE TABLE IF NOT EXISTS spreadsheets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sheet_id TEXT NOT NULL,
        group_id INTEGER NOT NULL,
        is_active INTEGER DEFAULT 1,
        last_hash TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE
    );
    """,
    """
    -- 3. Users
    CREATE TABLE IF NOT EXISTS users (
        chat_id INTEGER PRIMARY KEY,
        group_id INTEGER,
        username TEXT,
        first_name TEXT,
        is_banned INTEGER NOT NULL DEFAULT 0,
        locale TEXT NOT NULL DEFAULT 'ru',
        notifications_enabled INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        
        FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE SET NULL
    );
    """,
    """
    -- 4. Schedule-Lectures
    CREATE TABLE IF NOT EXISTS schedule_lectures (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sheet_id TEXT NOT NULL,
        group_id INTEGER NOT NULL,
        lecture_date TEXT NOT NULL,
        time TEXT,
        subject TEXT NOT NULL,
        room TEXT,
        teacher TEXT,
        form TEXT,
        hours REAL,
        course_year INTEGER,
        level TEXT,
        delivery_mode TEXT,
        course_notes TEXT,
        cell_note TEXT,

        FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE
    );
    """,
    """
    -- 5. Schedule Cache
    CREATE TABLE IF NOT EXISTS schedule_cache (
        sheet_id TEXT PRIMARY KEY,
        snapshot_path TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        academic_year INTEGER NOT NULL,
        loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    -- 6. Submissions Cache because kostyly velosipedy kto pridumal tolko 64-bit callbacks
    CREATE TABLE IF NOT EXISTS pending_submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER NOT NULL,
        group_name TEXT NOT NULL,
        sheet_id TEXT NOT NULL,
        user_chat_id INTEGER NOT NULL
    );
    """,
    """
    -- 7. Per-user notification delivery queue
    CREATE TABLE IF NOT EXISTS pending_notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        notification_type TEXT NOT NULL DEFAULT 'schedule_change',
        notification_key TEXT NOT NULL,
        sheet_id TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        group_id INTEGER NOT NULL,
        group_name TEXT NOT NULL,
        chat_id INTEGER NOT NULL,
        scheduled_for TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        delivered_at TIMESTAMP,

        UNIQUE(notification_type, notification_key, chat_id)
    );
    """,
)

REQUIRED_COLUMNS = {
    "groups": {
        "id": "INTEGER",
        "study_form": "TEXT",
        "enrollment_year": "INTEGER",
        "group_name": "TEXT",
    },
    "spreadsheets": {
        "id": "INTEGER",
        "sheet_id": "TEXT",
        "group_id": "INTEGER",
        "is_active": "INTEGER",
        "last_hash": "TEXT",
        "updated_at": "TIMESTAMP",
    },
    "users": {
        "chat_id": "INTEGER",
        "group_id": "INTEGER",
        "username": "TEXT",
        "first_name": "TEXT",
        "is_banned": "INTEGER",
        "locale": "TEXT",
        "notifications_enabled": "INTEGER",
        "created_at": "TIMESTAMP",
    },
    "schedule_lectures": {
        "id": "INTEGER",
        "sheet_id": "TEXT",
        "group_id": "INTEGER",
        "lecture_date": "TEXT",
        "time": "TEXT",
        "subject": "TEXT",
        "room": "TEXT",
        "teacher": "TEXT",
        "form": "TEXT",
        "hours": "REAL",
        "course_year": "INTEGER",
        "level": "TEXT",
        "delivery_mode": "TEXT",
        "course_notes": "TEXT",
        "cell_note": "TEXT",
    },
    "schedule_cache": {
        "sheet_id": "TEXT",
        "snapshot_path": "TEXT",
        "content_hash": "TEXT",
        "academic_year": "INTEGER",
        "loaded_at": "TIMESTAMP",
    },
    "pending_submissions": {
        "id": "INTEGER",
        "group_id": "INTEGER",
        "group_name": "TEXT",
        "sheet_id": "TEXT",
        "user_chat_id": "INTEGER",
    },
    "pending_notifications": {
        "id": "INTEGER",
        "notification_type": "TEXT",
        "notification_key": "TEXT",
        "sheet_id": "TEXT",
        "content_hash": "TEXT",
        "group_id": "INTEGER",
        "group_name": "TEXT",
        "chat_id": "INTEGER",
        "scheduled_for": "TIMESTAMP",
        "created_at": "TIMESTAMP",
        "delivered_at": "TIMESTAMP",
    },
}


class InitialSchemaMigration(Migration):
    """Migration class for the initial schema."""

    @property
    def version(self) -> int:
        return 1


    @property
    def name(self) -> str:
        return "initial_schema"


    def upgrade(self, conn: sqlite3.Connection) -> None:
        """Applies the initial schema to the database."""
        for statement in BASELINE_TABLES:
            conn.execute(statement)

        expected_tables = set(REQUIRED_COLUMNS)
        actual_tables = self.get_table_names(conn)

        missing = expected_tables - actual_tables
        if missing:
            raise ValueError(f"Missing baseline tables: {sorted(missing)}")

        for table in expected_tables:
            if not self.get_columns(conn, table):
                raise ValueError(f"Table '{table}' has no columns defined.")

        self._upgrade_legacy_users(conn)
        self._upgrade_legacy_pending_notifications(conn)

        for table, definitions in REQUIRED_COLUMNS.items():
            self.validate_columns(conn, table, set(definitions))

        self.validate_primary_key(conn, "groups", ("id",))
        self.validate_primary_key(conn, "spreadsheets", ("id",))
        self.validate_primary_key(conn, "users", ("chat_id",))
        self.validate_primary_key(conn, "schedule_lectures", ("id",))
        self.validate_primary_key(conn, "schedule_cache", ("sheet_id",))
        self.validate_primary_key(conn, "pending_submissions", ("id",))
        self.validate_primary_key(conn, "pending_notifications", ("id",))

        self.validate_foreign_keys(
        conn,
        "spreadsheets",
        {("group_id", "groups", "id", "NO ACTION", "CASCADE")},
        )

        self.validate_foreign_keys(
            conn,
            "users",
            {("group_id", "groups", "id", "NO ACTION", "SET NULL")},
        )

        self.validate_foreign_keys(
            conn,
            "schedule_lectures",
            {("group_id", "groups", "id", "NO ACTION", "CASCADE")},
        )

        for table in (
            "groups",
            "schedule_cache",
            "pending_submissions",
            "pending_notifications",
        ):
            self.validate_foreign_keys(conn, table, set())

        self.require_unique_columns(
            conn, "groups", ("study_form", "enrollment_year")
        )

        self.require_unique_columns(
            conn,
            "pending_notifications",
            ("notification_type", "notification_key", "chat_id"),
        )

        Migration.recreate_index(
            conn,
            "idx_spreadsheets_group",
            "spreadsheets",
            ["group_id"]
        )

        Migration.recreate_index(
            conn,
            "idx_users_group",
            "users",
            ["group_id", "notifications_enabled"]
        )

        Migration.recreate_index(
            conn,
            "idx_schedule_group_date",
            "schedule_lectures",
            ["group_id", "lecture_date"]
        )

        Migration.recreate_index(
            conn,
            "idx_schedule_sheet",
            "schedule_lectures",
            ["sheet_id"]
        )

        Migration.recreate_index(
            conn,
            "idx_pending_notifications_delivery",
            "pending_notifications",
            ["sheet_id", "content_hash", "delivered_at"]
        )

    @staticmethod
    def _upgrade_legacy_users(conn: sqlite3.Connection) -> None:
        """Add only the user columns introduced by the legacy initializer."""
        columns = Migration.get_columns(conn, "users")
        legacy_columns = {
            "username": "TEXT",
            "first_name": "TEXT",
            "is_banned": "INTEGER NOT NULL DEFAULT 0",
            "locale": "TEXT NOT NULL DEFAULT 'ru'",
        }
        for column, definition in legacy_columns.items():
            if column not in columns:
                Migration.add_column(conn, "users", column, definition)

    @staticmethod
    def _upgrade_legacy_pending_notifications(
        conn: sqlite3.Connection,
    ) -> None:
        """Migrate the pre-notification-type queue without fabricating other data."""
        columns = Migration.get_columns(conn, "pending_notifications")
        if "notification_type" in columns:
            return

        introduced_columns = {"notification_type", "notification_key", "scheduled_for"}
        partial_upgrade = columns & introduced_columns
        if partial_upgrade:
            raise ValueError(
                "Cannot migrate pending_notifications; incomplete legacy upgrade "
                f"contains columns: {sorted(partial_upgrade)}"
            )

        legacy_columns = {
            "id",
            "sheet_id",
            "content_hash",
            "group_id",
            "group_name",
            "chat_id",
            "created_at",
            "delivered_at",
        }
        missing = legacy_columns - columns
        if missing:
            raise ValueError(
                "Cannot migrate pending_notifications; missing legacy columns: "
                f"{sorted(missing)}"
            )

        Migration.add_column(
            conn,
            "pending_notifications",
            "notification_type",
            "TEXT NOT NULL DEFAULT 'schedule_change'",
        )
        Migration.add_column(
            conn,
            "pending_notifications",
            "notification_key",
            "TEXT NOT NULL DEFAULT ''",
        )
        Migration.add_column(
            conn,
            "pending_notifications",
            "scheduled_for",
            "TIMESTAMP",
        )
        conn.execute(
            """
            UPDATE pending_notifications
            SET notification_key = content_hash
            WHERE notification_key = ''
            """
        )

        conn.execute("DROP INDEX IF EXISTS idx_pending_notifications_delivery")
        conn.execute(
            "ALTER TABLE pending_notifications "
            "RENAME TO pending_notifications_legacy"
        )
        conn.execute(
            """
            CREATE TABLE pending_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                notification_type TEXT NOT NULL DEFAULT 'schedule_change',
                notification_key TEXT NOT NULL,
                sheet_id TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                group_id INTEGER NOT NULL,
                group_name TEXT NOT NULL,
                chat_id INTEGER NOT NULL,
                scheduled_for TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                delivered_at TIMESTAMP,
                UNIQUE(notification_type, notification_key, chat_id)
            )
            """
        )
        conn.execute(
            """
            INSERT INTO pending_notifications (
                id, notification_type, notification_key, sheet_id, content_hash,
                group_id, group_name, chat_id, scheduled_for, created_at, delivered_at
            )
            SELECT
                id, notification_type, notification_key, sheet_id, content_hash,
                group_id, group_name, chat_id, scheduled_for, created_at, delivered_at
            FROM pending_notifications_legacy
            """
        )
        conn.execute("DROP TABLE pending_notifications_legacy")
    
