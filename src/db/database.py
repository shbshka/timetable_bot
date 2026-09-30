from contextlib import contextmanager
import sqlite3
from pathlib import Path
from typing import Iterator
from src.utils.logger import get_logger
from src.parser.academic_year import enrollment_year

from config import DB_PATH, STUDY_FORMS, YEARS

logger = get_logger("database")


@contextmanager
def get_db_connection(db_path: Path = DB_PATH) -> Iterator[sqlite3.Connection]:
    """Creates a database connection with foreign keys enabled."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Path = DB_PATH) -> None:
    """Initializes SQLite database tables and performance indexes."""
    db_path.parent.mkdir(parents=True, exist_ok=True)

    create_tables_script = """
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

    -- 5. Schedule Cache
    CREATE TABLE IF NOT EXISTS schedule_cache (
        sheet_id TEXT PRIMARY KEY,
        snapshot_path TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        academic_year INTEGER NOT NULL,
        loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- 6. Submissions Cache because kostyly velosipedy kto pridumal tolko 64-bit callbacks
    CREATE TABLE IF NOT EXISTS pending_submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER NOT NULL,
        group_name TEXT NOT NULL,
        sheet_id TEXT NOT NULL,
        user_chat_id INTEGER NOT NULL
    );

    -- 7. Performance Indexes
    CREATE INDEX IF NOT EXISTS idx_spreadsheets_group ON spreadsheets(group_id);
    CREATE INDEX IF NOT EXISTS idx_users_group ON users(group_id, notifications_enabled);
    CREATE INDEX IF NOT EXISTS idx_schedule_group_date ON schedule_lectures(group_id, lecture_date);
    CREATE INDEX IF NOT EXISTS idx_schedule_sheet ON schedule_lectures(sheet_id);
    """

    try:
        with get_db_connection(db_path) as conn:
            conn.executescript(create_tables_script)

            user_columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
            pending_columns = {row["name"] for row in conn.execute("PRAGMA table_info(pending_submissions)")}

            for column_name, column_type in (
                ("username", "TEXT"),
                ("first_name", "TEXT"),
                ("is_banned", "INTEGER NOT NULL DEFAULT 0"),
                ("locale", "TEXT NOT NULL DEFAULT 'ru'"),
            ):
                if column_name not in user_columns:
                    conn.execute(f"ALTER TABLE users ADD COLUMN {column_name} {column_type}")
            logger.info(f"Database initialized successfully at '{db_path}'.")
    except sqlite3.Error as e:
        logger.error(f"Failed to initialize database: {e}", exc_info=True)
        raise


def populate_db(db_path: Path = DB_PATH) -> None:
    """Populates the database with initial data."""
    try:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()

            for form in STUDY_FORMS:
                for year_num in YEARS:
                    group_enrollment_year = enrollment_year(year_num)

                    cursor.execute("""
                        INSERT INTO groups (study_form, enrollment_year)
                        VALUES (?, ?)
                        ON CONFLICT(study_form, enrollment_year) DO UPDATE 
                        SET study_form=excluded.study_form, 
                        enrollment_year=excluded.enrollment_year
                    """, (form, group_enrollment_year))
    except sqlite3.Error as e:
        logger.error(f"Failed to populate database: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    init_db()