import sqlite3

from src.db.migrations.base import Migration
from src.db.migrations.m001_initial_schema import BASELINE_TABLES


class OptimizedSchemaMigration(Migration):
    """Convert the initial schema into the optimized relational schema."""

    @property
    def version(self) -> int:
        return 2

    @property
    def name(self) -> str:
        return "optimized_schema"

    def upgrade(self, conn: sqlite3.Connection) -> None:
        self._rename_source_tables(conn)
        self._create_tables(conn)
        self._copy_data(conn)
        self._drop_source_tables(conn)
        self._validate_result(conn)

    def downgrade(self, conn: sqlite3.Connection) -> None:
        """Convert the optimized schema back to the initial schema."""
        self._rename_optimized_tables(conn)
        for statement in BASELINE_TABLES:
            conn.execute(statement)
        self._copy_data_to_initial_schema(conn)
        self._create_initial_indexes(conn)
        self._drop_renamed_optimized_tables(conn)

    @staticmethod
    def _rename_optimized_tables(conn: sqlite3.Connection) -> None:
        for table in (
            "groups",
            "spreadsheets",
            "spreadsheets_groups",
            "lectures",
            "users",
            "notification_preferences",
            "notification_status",
            "notifications_queue",
            "pending_spreadsheets",
            "spreadsheets_cache",
        ):
            conn.execute(
                f'ALTER TABLE "{table}" RENAME TO "{table}_optimized"'
            )

    @staticmethod
    def _copy_data_to_initial_schema(conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            INSERT INTO groups (id, study_form, enrollment_year)
            SELECT id, study_form, enrollment_year
            FROM groups_optimized
            """
        )
        conn.execute(
            """
            INSERT INTO spreadsheets (
                id, sheet_id, group_id, is_active, last_hash, updated_at
            )
            SELECT sg.id, sg.sheet_id, sg.group_id, sg.is_active,
                   s.last_hash, s.updated_at
            FROM spreadsheets_groups_optimized sg
            JOIN spreadsheets_optimized s ON s.sheet_id = sg.sheet_id
            JOIN groups_optimized g ON g.id = sg.group_id
            """
        )
        conn.execute(
            """
            INSERT INTO users (
                chat_id, group_id, username, first_name, is_banned, locale,
                notifications_enabled, created_at
            )
            SELECT u.chat_id, u.group_id, u.username, u.name, u.is_banned,
                   u.locale,
                   COALESCE((
                       SELECT p.is_enabled
                       FROM notification_preferences_optimized p
                       WHERE p.recipient_id = u.chat_id
                         AND p.type = 'schedule_change'
                   ), 1),
                   u.created_at
            FROM users_optimized u
            """
        )
        conn.execute(
            """
            INSERT INTO schedule_lectures (
                id, sheet_id, group_id, lecture_date, time, subject, room,
                teacher, delivery_mode, course_notes, cell_note
            )
            SELECT id, source_id, group_id, lecture_date, lecture_time, subject,
                   room, teacher, delivery_mode, course_notes, cell_note
            FROM lectures_optimized
            """
        )
        conn.execute(
            """
            INSERT INTO schedule_cache (
                sheet_id, snapshot_path, content_hash, academic_year, loaded_at
            )
            SELECT c.sheet_id, c.snapshot_path, c.content_hash,
                   s.academic_starting_year, c.loaded_at
            FROM spreadsheets_cache_optimized c
            JOIN spreadsheets_optimized s ON s.sheet_id = c.sheet_id
            """
        )
        conn.execute(
            """
            INSERT INTO pending_submissions (
                id, group_id, group_name, sheet_id, user_chat_id
            )
            SELECT p.id, p.target_group_id, g.group_name,
                   p.submitted_spreadsheet_id, p.sender_id
            FROM pending_spreadsheets_optimized p
            JOIN groups_optimized g ON g.id = p.target_group_id
            """
        )
        conn.execute(
            """
            INSERT INTO pending_notifications (
                id, notification_type, notification_key, sheet_id, content_hash,
                group_id, group_name, chat_id, scheduled_for, created_at,
                delivered_at
            )
            SELECT q.id, 'schedule_change',
                   p.type || ':' || q.scheduled_for,
                   CASE
                       WHEN instr(p.type, ':') > 0
                       THEN substr(p.type, 17, instr(substr(p.type, 17), ':') - 1)
                       ELSE ''
                   END,
                   CASE
                       WHEN instr(p.type, ':') > 0
                            AND instr(substr(p.type, 17), ':') > 0
                       THEN substr(
                           p.type,
                           17 + instr(substr(p.type, 17), ':')
                       )
                       ELSE p.type
                   END,
                   COALESCE(u.group_id, 0),
                   COALESCE(g.group_name, ''),
                   p.recipient_id,
                   q.scheduled_for,
                   q.status_updated_at,
                   CASE WHEN q.status_id = 2 THEN q.status_updated_at END
            FROM notifications_queue_optimized q
            JOIN notification_preferences_optimized p
              ON p.id = q.notification_id
            JOIN users_optimized u ON u.chat_id = p.recipient_id
            LEFT JOIN groups_optimized g ON g.id = u.group_id
            WHERE u.group_id IS NOT NULL
            """
        )

    @staticmethod
    def _create_initial_indexes(conn: sqlite3.Connection) -> None:
        Migration.recreate_index(
            conn, "idx_spreadsheets_group", "spreadsheets", ["group_id"]
        )
        Migration.recreate_index(
            conn, "idx_users_group", "users",
            ["group_id", "notifications_enabled"],
        )
        Migration.recreate_index(
            conn, "idx_schedule_group_date", "schedule_lectures",
            ["group_id", "lecture_date"],
        )
        Migration.recreate_index(
            conn, "idx_schedule_sheet", "schedule_lectures", ["sheet_id"]
        )
        Migration.recreate_index(
            conn, "idx_pending_notifications_delivery",
            "pending_notifications",
            ["sheet_id", "content_hash", "delivered_at"],
        )

    @staticmethod
    def _drop_renamed_optimized_tables(conn: sqlite3.Connection) -> None:
        for table in (
            "spreadsheets_cache_optimized",
            "pending_spreadsheets_optimized",
            "notifications_queue_optimized",
            "notification_status_optimized",
            "notification_preferences_optimized",
            "lectures_optimized",
            "spreadsheets_groups_optimized",
            "users_optimized",
            "spreadsheets_optimized",
            "groups_optimized",
        ):
            conn.execute(f'DROP TABLE "{table}"')

    @staticmethod
    def _rename_source_tables(conn: sqlite3.Connection) -> None:
        for index in (
            "idx_spreadsheets_group",
            "idx_users_group",
            "idx_schedule_group_date",
            "idx_schedule_sheet",
            "idx_pending_notifications_delivery",
        ):
            conn.execute(f'DROP INDEX IF EXISTS "{index}"')

        for table in (
            "groups",
            "spreadsheets",
            "users",
            "schedule_lectures",
            "schedule_cache",
            "pending_submissions",
            "pending_notifications",
        ):
            conn.execute(f'ALTER TABLE "{table}" RENAME TO "{table}_legacy"')

    @staticmethod
    def _create_tables(conn: sqlite3.Connection) -> None:
        schema = """
            CREATE TABLE groups (
                id INTEGER PRIMARY KEY,
                study_form TEXT NOT NULL,
                enrollment_year INTEGER NOT NULL
                    CHECK (enrollment_year BETWEEN 2000 AND 2100),
                group_name TEXT NOT NULL,
                UNIQUE(study_form, enrollment_year)
            );

            CREATE TABLE spreadsheets (
                sheet_id TEXT PRIMARY KEY CHECK (sheet_id != ''),
                academic_starting_year INTEGER NOT NULL
                    CHECK (academic_starting_year BETWEEN 2000 AND 2100),
                last_hash TEXT,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE spreadsheets_groups (
                id INTEGER PRIMARY KEY,
                sheet_id TEXT NOT NULL
                    REFERENCES spreadsheets(sheet_id) ON DELETE CASCADE,
                group_id INTEGER NOT NULL
                    REFERENCES groups(id) ON DELETE CASCADE,
                is_active INTEGER NOT NULL DEFAULT 1
                    CHECK (is_active IN (0, 1)),
                attached_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(sheet_id, group_id, is_active)
            );

            CREATE TABLE lectures (
                id INTEGER PRIMARY KEY,
                source_id TEXT NOT NULL
                    REFERENCES spreadsheets(sheet_id) ON DELETE CASCADE,
                group_id INTEGER NOT NULL
                    REFERENCES groups(id) ON DELETE CASCADE,
                lecture_date TEXT NOT NULL,
                lecture_time TEXT,
                subject TEXT NOT NULL CHECK (subject != ''),
                room TEXT,
                teacher TEXT,
                duration_academic_hours REAL
                    CHECK (
                        duration_academic_hours IS NULL
                        OR duration_academic_hours >= 0
                    ),
                delivery_mode TEXT,
                course_notes TEXT,
                cell_note TEXT
            );

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
            );

            CREATE TABLE notification_preferences (
                id INTEGER PRIMARY KEY,
                type TEXT NOT NULL CHECK (type != ''),
                recipient_id INTEGER NOT NULL
                    REFERENCES users(chat_id) ON DELETE CASCADE,
                is_enabled INTEGER NOT NULL DEFAULT 1
                    CHECK (is_enabled IN (0, 1)),
                UNIQUE(recipient_id, type)
            );

            CREATE TABLE notification_status (
                id INTEGER PRIMARY KEY,
                status TEXT NOT NULL UNIQUE
            );

            CREATE TABLE notifications_queue (
                id INTEGER PRIMARY KEY,
                notification_id INTEGER NOT NULL
                    REFERENCES notification_preferences(id) ON DELETE CASCADE,
                scheduled_for TIMESTAMP NOT NULL,
                status_id INTEGER NOT NULL
                    REFERENCES notification_status(id) ON DELETE RESTRICT,
                status_updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(notification_id, scheduled_for)
            );

            CREATE TABLE pending_spreadsheets (
                id INTEGER PRIMARY KEY,
                sender_id INTEGER NOT NULL
                    REFERENCES users(chat_id) ON DELETE CASCADE,
                target_group_id INTEGER NOT NULL
                    REFERENCES groups(id) ON DELETE CASCADE,
                submitted_spreadsheet_id TEXT NOT NULL
                    CHECK (submitted_spreadsheet_id != ''),
                submission_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE spreadsheets_cache (
                sheet_id TEXT PRIMARY KEY
                    REFERENCES spreadsheets(sheet_id) ON DELETE CASCADE,
                snapshot_path TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                loaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX idx_spreadsheets_groups_group
                ON spreadsheets_groups(group_id);
            CREATE INDEX idx_users_group ON users(group_id);
        """
        for statement in schema.split(";\n"):
            conn.execute(statement)

    @staticmethod
    def _copy_data(conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            INSERT INTO groups (id, study_form, enrollment_year, group_name)
            SELECT id, study_form, enrollment_year,
                   PRINTF('%02d', enrollment_year % 100) || study_form
            FROM groups_legacy
            WHERE enrollment_year BETWEEN 2000 AND 2100
            """
        )
        conn.execute(
            """
            INSERT INTO spreadsheets (
                sheet_id, academic_starting_year, last_hash, updated_at
            )
            SELECT s.sheet_id,
                   COALESCE(
                       (SELECT CASE
                                   WHEN academic_year BETWEEN 2000 AND 2100
                                   THEN academic_year
                               END
                        FROM schedule_cache_legacy
                        WHERE sheet_id = s.sheet_id),
                       (SELECT MIN(g2.enrollment_year)
                        FROM spreadsheets_legacy s2
                        JOIN groups_legacy g2 ON g2.id = s2.group_id
                        WHERE s2.sheet_id = s.sheet_id)
                   ),
                   (SELECT s2.last_hash
                    FROM spreadsheets_legacy s2
                    WHERE s2.sheet_id = s.sheet_id
                    ORDER BY s2.is_active DESC, s2.updated_at DESC, s2.id DESC
                    LIMIT 1),
                   COALESCE(
                       (SELECT s2.updated_at
                        FROM spreadsheets_legacy s2
                        WHERE s2.sheet_id = s.sheet_id
                        ORDER BY s2.is_active DESC, s2.updated_at DESC, s2.id DESC
                        LIMIT 1),
                       CURRENT_TIMESTAMP
                   )
            FROM spreadsheets_legacy s
            WHERE s.sheet_id <> ''
              AND EXISTS (
                  SELECT 1
                  FROM groups_legacy g
                  WHERE g.id = s.group_id
                    AND g.enrollment_year BETWEEN 2000 AND 2100
              )
            GROUP BY s.sheet_id
            """
        )
        conn.execute(
            """
            INSERT INTO spreadsheets_groups (
                id, sheet_id, group_id, is_active, attached_at
            )
            SELECT MIN(id), sheet_id, group_id, is_active,
                   COALESCE(MIN(updated_at), CURRENT_TIMESTAMP)
            FROM spreadsheets_legacy
            WHERE sheet_id <> ''
              AND is_active IN (0, 1)
              AND EXISTS (
                  SELECT 1
                  FROM spreadsheets s
                  WHERE s.sheet_id = spreadsheets_legacy.sheet_id
              )
              AND EXISTS (
                  SELECT 1
                  FROM groups g
                  WHERE g.id = spreadsheets_legacy.group_id
                    AND g.enrollment_year BETWEEN 2000 AND 2100
              )
            GROUP BY sheet_id, group_id, is_active
            """
        )
        conn.execute(
            """
            INSERT INTO lectures (
                id, source_id, group_id, lecture_date, lecture_time, subject,
                room, teacher, duration_academic_hours, delivery_mode,
                course_notes, cell_note
            )
            SELECT id, sheet_id, group_id, lecture_date, time, subject, room,
                   teacher, hours, delivery_mode, course_notes, cell_note
            FROM schedule_lectures_legacy
            WHERE subject <> ''
              AND (hours IS NULL OR hours >= 0)
              AND EXISTS (
                  SELECT 1
                  FROM spreadsheets s
                  WHERE s.sheet_id = schedule_lectures_legacy.sheet_id
              )
              AND EXISTS (
                  SELECT 1
                  FROM groups g
                  WHERE g.id = schedule_lectures_legacy.group_id
                    AND g.enrollment_year BETWEEN 2000 AND 2100
              )
            """
        )
        conn.execute(
            """
            INSERT INTO users (
                chat_id, group_id, username, name, locale, is_banned, created_at
            )
            SELECT chat_id, group_id, username, first_name,
                   COALESCE(locale, 'ru'), COALESCE(is_banned, 0),
                   COALESCE(created_at, CURRENT_TIMESTAMP)
            FROM users_legacy
            WHERE COALESCE(locale, 'ru') IN ('ru', 'en')
              AND COALESCE(is_banned, 0) IN (0, 1)
            """
        )
        conn.execute(
            """
            INSERT INTO notification_preferences (
                id, type, recipient_id, is_enabled
            )
            SELECT -chat_id, 'schedule_change', chat_id,
                   COALESCE(notifications_enabled, 1)
            FROM users_legacy
            WHERE COALESCE(locale, 'ru') IN ('ru', 'en')
              AND COALESCE(is_banned, 0) IN (0, 1)
            """
        )
        conn.execute(
            """
            INSERT INTO notification_preferences (id, type, recipient_id)
            SELECT 1000000000 + ROW_NUMBER() OVER (
                       ORDER BY notification_type, chat_id
                   ),
                   notification_type,
                   chat_id
            FROM (
                SELECT DISTINCT notification_type, chat_id
                FROM pending_notifications_legacy
                WHERE notification_type <> ''
                  AND notification_type <> 'schedule_change'
            )
            WHERE EXISTS (
                SELECT 1
                FROM users u
                WHERE u.chat_id = chat_id
            )
            """
        )
        conn.executemany(
            "INSERT INTO notification_status (id, status) VALUES (?, ?)",
            ((1, "pending"), (2, "delivered")),
        )
        conn.execute(
            """
            INSERT INTO notifications_queue (
                id, notification_id, scheduled_for, status_id, status_updated_at
            )
            SELECT n.id, p.id,
                   datetime(
                       COALESCE(n.scheduled_for, n.created_at, CURRENT_TIMESTAMP),
                       printf(
                           '+%d seconds',
                           ROW_NUMBER() OVER (
                               PARTITION BY p.id, COALESCE(
                                   n.scheduled_for, n.created_at, CURRENT_TIMESTAMP
                               )
                               ORDER BY n.id
                           ) - 1
                       )
                   ),
                   CASE WHEN n.delivered_at IS NULL THEN 1 ELSE 2 END,
                   COALESCE(n.delivered_at, n.created_at, CURRENT_TIMESTAMP)
            FROM pending_notifications_legacy n
            JOIN notification_preferences p
              ON p.recipient_id = n.chat_id AND p.type = n.notification_type
            WHERE n.notification_type <> ''
              AND EXISTS (
                  SELECT 1
                  FROM users u
                  WHERE u.chat_id = n.chat_id
              )
            """
        )
        conn.execute(
            """
            INSERT INTO pending_spreadsheets (
                id, sender_id, target_group_id, submitted_spreadsheet_id,
                submission_time
            )
            SELECT id, user_chat_id, group_id, sheet_id,
                   CURRENT_TIMESTAMP
            FROM pending_submissions_legacy
            WHERE sheet_id <> ''
              AND EXISTS (
                  SELECT 1 FROM users u WHERE u.chat_id = user_chat_id
              )
              AND EXISTS (
                  SELECT 1
                  FROM groups g
                  WHERE g.id = group_id
                    AND g.enrollment_year BETWEEN 2000 AND 2100
              )
            """
        )
        conn.execute(
            """
            INSERT INTO spreadsheets_cache (
                sheet_id, snapshot_path, content_hash, loaded_at
            )
            SELECT sheet_id, snapshot_path, content_hash, loaded_at
            FROM schedule_cache_legacy
            WHERE EXISTS (
                SELECT 1
                FROM spreadsheets s
                WHERE s.sheet_id = schedule_cache_legacy.sheet_id
            )
            """
        )

    @staticmethod
    def _drop_source_tables(conn: sqlite3.Connection) -> None:
        for table in (
            "pending_notifications_legacy",
            "pending_submissions_legacy",
            "schedule_lectures_legacy",
            "schedule_cache_legacy",
            "spreadsheets_legacy",
            "users_legacy",
            "groups_legacy",
        ):
            conn.execute(f'DROP TABLE "{table}"')

    @staticmethod
    def _validate_result(conn: sqlite3.Connection) -> None:
        violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise ValueError(f"Planned schema has foreign-key violations: {violations[:5]}")
