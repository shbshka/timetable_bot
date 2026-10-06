import sqlite3

import pytest

from src.db.migrate import run_migrations
from src.db.migrations.base import Migration
from src.db.migrations.m001_initial_schema import (
    BASELINE_TABLES,
    REQUIRED_COLUMNS,
)


class ConcreteMigration(Migration):
    @property
    def version(self) -> int:
        return 99

    @property
    def name(self) -> str:
        return "test"

    def upgrade(self, conn: sqlite3.Connection) -> None:
        conn.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY)")


def test_base_helpers_read_and_validate_table_shape() -> None:
    # Arrange
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)")

    # Act
    columns = Migration.get_columns(connection, "items")
    table_names = Migration.get_table_names(connection)

    # Assert
    assert columns == {"id", "name"}
    assert "items" in table_names


def test_base_helpers_add_and_validate_columns() -> None:
    # Arrange
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE items (id INTEGER PRIMARY KEY)")

    # Act
    Migration.add_column(connection, "items", "name", "TEXT")
    Migration.add_missing_columns(
        connection,
        "items",
        {"name": "TEXT", "enabled": "INTEGER DEFAULT 1"},
    )

    # Assert
    assert Migration.get_columns(connection, "items") == {"id", "name", "enabled"}
    Migration.validate_columns(connection, "items", {"id", "name", "enabled"})


def test_base_helpers_reject_unexpected_columns() -> None:
    # Arrange
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, extra TEXT)")

    # Act
    validation = pytest.raises(
        ValueError,
        Migration.validate_columns,
        connection,
        "items",
        {"id"},
    )

    # Assert
    assert "Extra" in str(validation.value)


def test_base_helpers_validate_keys_indexes_and_quoting() -> None:
    # Arrange
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
    connection.execute(
        """
        CREATE TABLE child (
            id INTEGER PRIMARY KEY,
            parent_id INTEGER,
            FOREIGN KEY (parent_id) REFERENCES parent(id) ON DELETE CASCADE
        )
        """
    )
    connection.execute("CREATE UNIQUE INDEX unique_child_parent ON child(parent_id)")

    # Act
    Migration.validate_primary_key(connection, "child", ("id",))
    Migration.validate_foreign_keys(
        connection,
        "child",
        {("parent_id", "parent", "id", "NO ACTION", "CASCADE")},
    )
    Migration.require_unique_columns(connection, "child", ("parent_id",))
    Migration.recreate_index(connection, "child_parent", "child", ["parent_id"])

    # Assert
    assert Migration.quote_identifier('a"b') == '"a""b"'
    assert any(
        row[1] == "child_parent"
        for row in connection.execute("PRAGMA index_list(child)")
    )


def test_initial_migration_applies_to_an_isolated_database(tmp_path) -> None:
    # Arrange
    database_path = tmp_path / "isolated.db"

    # Act
    run_migrations(database_path)

    # Assert
    connection = sqlite3.connect(database_path)
    assert connection.execute(
        "SELECT version, name FROM schema_migrations"
    ).fetchall() == [(1, "initial_schema")]
    for table, columns in REQUIRED_COLUMNS.items():
        assert Migration.get_columns(connection, table) == set(columns)


def test_initial_migration_is_idempotent_on_an_isolated_database(tmp_path) -> None:
    # Arrange
    database_path = tmp_path / "isolated.db"
    run_migrations(database_path)

    # Act
    run_migrations(database_path)

    # Assert
    connection = sqlite3.connect(database_path)
    assert connection.execute(
        "SELECT COUNT(*) FROM schema_migrations"
    ).fetchone()[0] == 1


def test_migration_runner_rejects_unknown_migration_history(tmp_path) -> None:
    # Arrange
    database_path = tmp_path / "incompatible.db"
    connection = sqlite3.connect(database_path)
    connection.execute(
        "CREATE TABLE schema_migrations ("
        "version INTEGER PRIMARY KEY, name TEXT NOT NULL)"
    )
    connection.execute(
        "INSERT INTO schema_migrations(version, name) VALUES (1, 'old_name')"
    )
    connection.commit()
    connection.close()

    # Act
    migration = pytest.raises(RuntimeError, run_migrations, database_path)

    # Assert
    assert "history is incompatible" in str(migration.value)


def test_initial_migration_preserves_legacy_init_db_data(tmp_path) -> None:
    # Arrange
    database_path = tmp_path / "legacy.db"
    connection = sqlite3.connect(database_path)
    for statement in BASELINE_TABLES:
        connection.execute(statement)
    connection.execute("DROP TABLE users")
    connection.execute(
        """
        CREATE TABLE users (
            chat_id INTEGER PRIMARY KEY,
            group_id INTEGER,
            notifications_enabled INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE SET NULL
        )
        """
    )
    connection.execute("INSERT INTO users(chat_id) VALUES (42)")
    connection.execute("DROP TABLE pending_notifications")
    connection.execute(
        """
        CREATE TABLE pending_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sheet_id TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            group_id INTEGER NOT NULL,
            group_name TEXT NOT NULL,
            chat_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            delivered_at TIMESTAMP
        )
        """
    )
    connection.execute(
        """
        INSERT INTO pending_notifications(
            sheet_id, content_hash, group_id, group_name, chat_id
        ) VALUES ('sheet', 'hash', 1, '24HR', 42)
        """
    )
    connection.commit()
    connection.close()

    # Act
    run_migrations(database_path)

    # Assert
    connection = sqlite3.connect(database_path)
    assert connection.execute(
        "SELECT username, first_name, is_banned, locale FROM users WHERE chat_id = 42"
    ).fetchone() == (None, None, 0, "ru")
    assert connection.execute(
        """
        SELECT notification_type, notification_key, sheet_id, chat_id
        FROM pending_notifications
        """
    ).fetchone() == ("schedule_change", "hash", "sheet", 42)
    assert not connection.execute(
        "PRAGMA foreign_key_list(pending_notifications)"
    ).fetchall()


def test_initial_migration_rejects_unknown_missing_essential_column(tmp_path) -> None:
    # Arrange
    database_path = tmp_path / "invalid.db"
    connection = sqlite3.connect(database_path)
    for statement in BASELINE_TABLES:
        connection.execute(statement)
    connection.execute("ALTER TABLE schedule_cache RENAME TO schedule_cache_old")
    connection.execute(
        """
        CREATE TABLE schedule_cache (
            sheet_id TEXT PRIMARY KEY,
            snapshot_path TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.commit()
    connection.close()

    # Act
    migration = pytest.raises(ValueError, run_migrations, database_path)

    # Assert
    assert "academic_year" in str(migration.value)
