import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from warnings import deprecated

from config import DB_PATH, STUDY_FORMS, YEARS
from src.db.migrate import run_migrations
from src.parser.academic_year import enrollment_year
from src.utils.logger import get_logger

logger = get_logger("database")


@contextmanager
def get_db_connection(db_path: Path = DB_PATH) -> Iterator[sqlite3.Connection]:
    """Creates a database connection with foreign keys enabled."""
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()

@deprecated("Use run_migrations() directly instead of init_db() for clarity.")
def init_db(db_path: Path = DB_PATH) -> None:
    run_migrations(db_path)


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