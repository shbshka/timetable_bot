import sqlite3
from pathlib import Path

from config import DB_PATH
from src.db.migrations import m001_initial_schema, m002_optimized_schema
from src.utils.logger import get_logger

logger = get_logger("migrations")

initial = m001_initial_schema.InitialSchemaMigration()
optimized = m002_optimized_schema.OptimizedSchemaMigration()

MIGRATIONS = (
    (initial.version, initial.name, initial.upgrade),
    (optimized.version, optimized.name, optimized.upgrade),
)

def run_migrations(db_path: Path = DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(
        db_path,
        timeout=30,
        isolation_level=None,
    )

    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 30000")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        for version, name, upgrade in MIGRATIONS:

            logger.info(f"Applying migration {version}: {name}...")
            conn.execute("BEGIN IMMEDIATE")

            try:
                applied = dict(
                    conn.execute(
                        "SELECT version, name FROM schema_migrations"
                    ).fetchall()
                )

                known = {
                    migration_version: migration_name
                    for migration_version, migration_name, _ in MIGRATIONS
                }

                for applied_version, applied_name in applied.items():
                    if known.get(applied_version) != applied_name:
                        raise RuntimeError(
                            "Database migration history is incompatible "
                            "with this application version"
                        )

                if version in applied:
                    conn.commit()
                    continue

                upgrade(conn)

                violations = conn.execute(
                    "PRAGMA foreign_key_check"
                ).fetchall()
                if violations:
                    raise RuntimeError(
                        f"Migration {version} produced foreign-key violations: "
                        f"{violations[:5]}"
                    )

                conn.execute(
                    """
                    INSERT INTO schema_migrations (version, name)
                    VALUES (?, ?)
                    """,
                    (version, name),
                )

                conn.commit()
                logger.info(f"Migration {version} applied successfully.")

            except BaseException:
                conn.rollback()
                logger.error(f"Migration {version} failed. Rolled back changes.", exc_info=True)
                raise

    finally:
        conn.close()


if __name__ == "__main__":
    run_migrations()