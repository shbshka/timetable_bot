import sqlite3
from pathlib import Path

from config import DB_PATH
from src.db.migrations import m001_initial_schema, m002_optimized_schema
from src.utils.logger import get_logger

logger = get_logger("migrations")

initial = m001_initial_schema.InitialSchemaMigration()
optimized = m002_optimized_schema.OptimizedSchemaMigration()

MIGRATIONS = (
    (initial.version, initial.name, initial.upgrade, initial.downgrade),
    (optimized.version, optimized.name, optimized.upgrade, optimized.downgrade),
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

        for version, name, upgrade, _ in MIGRATIONS:

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
                    for migration_version, migration_name, _, _ in MIGRATIONS
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
                logger.exception(
                    f"Migration {version} failed. Rolled back changes."
                )
                raise

    finally:
        conn.close()


def run_downgrades(db_path: Path = DB_PATH, target_version: int = 0) -> None:
    """Revert applied migrations down to and including ``target_version``."""
    if target_version < 0:
        raise ValueError("target_version must not be negative")

    conn = sqlite3.connect(db_path, timeout=30, isolation_level=None)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 30000")
        applied = dict(conn.execute(
            "SELECT version, name FROM schema_migrations"
        ).fetchall())
        known = {
            migration_version: migration_name
            for migration_version, migration_name, _, _ in MIGRATIONS
        }
        if any(known.get(version) != name for version, name in applied.items()):
            raise RuntimeError(
                "Database migration history is incompatible "
                "with this application version"
            )

        for version, name, _, downgrade in reversed(MIGRATIONS):
            if version <= target_version or version not in applied:
                continue
            conn.execute("BEGIN IMMEDIATE")
            try:
                downgrade(conn)
                violations = conn.execute("PRAGMA foreign_key_check").fetchall()
                if violations:
                    raise RuntimeError(
                        f"Downgrade {version} produced foreign-key violations: "
                        f"{violations[:5]}"
                    )
                conn.execute(
                    "DELETE FROM schema_migrations WHERE version = ?",
                    (version,),
                )
                conn.commit()
                logger.info(f"Migration {version} downgraded successfully.")
            except BaseException:
                conn.rollback()
                logger.exception(
                    f"Migration {version} downgrade failed. Rolled back changes.",
                )
                raise
    finally:
        conn.close()


if __name__ == "__main__":
    run_migrations()