import sqlite3
from abc import ABC, abstractmethod


class Migration(ABC):
    @property
    @abstractmethod
    def version(self) -> int:
        """Unique, increasing migration number."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable migration name."""


    @abstractmethod
    def upgrade(self, conn: sqlite3.Connection) -> None:
        """Apply changes using the runner's transaction."""


    @abstractmethod
    def downgrade(self, conn: sqlite3.Connection) -> None:
        """Revert changes using the runner's transaction."""


    @staticmethod
    def get_columns(
        conn: sqlite3.Connection,
        table: str,
    ) -> set[str]:
        """Get the set of column names for a given table."""
        quoted_table = Migration.quote_identifier(table)

        return {
            row[1]
            for row in conn.execute(
                f"PRAGMA table_xinfo({quoted_table})"
            )
        }


    @staticmethod
    def add_column(
        conn: sqlite3.Connection,
        table: str,
        column: str,
        definition: str,
    ) -> None:
        """Add a new column to an existing table."""
        quoted_table = Migration.quote_identifier(table)
        conn.execute(
            f"ALTER TABLE {quoted_table} ADD COLUMN {column} {definition}"
        )


    @staticmethod
    def validate_columns(
        conn: sqlite3.Connection,
        table: str,
        expected_columns: set[str],
    ) -> None:
        """Raise an error if the table does not have the expected columns."""
        actual_columns = Migration.get_columns(conn, table)
        missing_columns = expected_columns - actual_columns
        extra_columns = actual_columns - expected_columns

        if missing_columns or extra_columns:
            raise ValueError(
                f"Table '{table}' has unexpected columns. "
                f"Missing: {missing_columns}, Extra: {extra_columns}"
            )

    @staticmethod
    def quote_identifier(identifier: str) -> str:
        """Quote an identifier to make it safe for use in SQL."""
        return '"' + identifier.replace('"', '""') + '"'

    @staticmethod
    def validate_foreign_keys(
        conn: sqlite3.Connection,
        table: str,
        expected: set[tuple[str, str, str, str, str]],
    ) -> None:
        """
        Validate that the foreign keys of a table match the expected set.
        expected: Set of tuples in the form:
        (local_column, parent_table, parent_column, on_update, on_delete)
        For the single-column foreign keys used in this baseline.
        """
        quoted = Migration.quote_identifier(table)

        actual = {
            (
                row[3],
                row[2],
                row[4],
                row[5].upper(),
                row[6].upper(),
            )
            for row in conn.execute(f"PRAGMA foreign_key_list({quoted})")
        }

        if actual != expected:
            raise ValueError(
                f"Unexpected foreign keys on {table}: "
                f"expected={expected}, actual={actual}"
            )


    @staticmethod
    def validate_primary_key(
        conn: sqlite3.Connection,
        table: str,
        expected: tuple[str, ...],
    ) -> None:
        quoted = Migration.quote_identifier(table)
        rows = conn.execute(f"PRAGMA table_xinfo({quoted})").fetchall()

        actual = tuple(
            row[1]
            for row in sorted(
                (row for row in rows if row[5] > 0),
                key=lambda row: row[5],
            )
        )

        if actual != expected:
            raise ValueError(
                f"Unexpected primary key on {table}: {actual}"
            )


    @staticmethod
    def require_unique_columns(
        conn: sqlite3.Connection,
        table: str,
        expected: tuple[str, ...],
    ) -> None:
        quoted = Migration.quote_identifier(table)

        for index in conn.execute(f"PRAGMA index_list({quoted})").fetchall():
            if not index[2] or index[4]:
                continue  # Nonunique or partial index.

            index_name = Migration.quote_identifier(index[1])
            columns = tuple(
                row[2]
                for row in conn.execute(
                    f"PRAGMA index_info({index_name})"
                )
            )

            if columns == expected:
                return

        raise ValueError(
            f"Missing full unique index on {table}{expected}"
        )


    @staticmethod
    def add_missing_columns(
        conn: sqlite3.Connection,
        table: str,
        expected_columns: dict[str, str],
    ) -> None:
        """Add any missing columns to the table."""
        actual_columns = Migration.get_columns(conn, table)
        for column_name, column_definition in expected_columns.items():
            if column_name not in actual_columns:
                Migration.add_column(conn, table, column_name, column_definition)


    @staticmethod
    def get_table_names(conn: sqlite3.Connection) -> set[str]:
        """Get the set of table names in the database."""
        return {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }


    @staticmethod
    def recreate_index(conn: sqlite3.Connection, index_name: str, table_name: str, column_list: list[str]) -> None:
        """Drop and recreate an index."""
        conn.execute(f"DROP INDEX IF EXISTS {index_name}")
        conn.execute(f"CREATE INDEX {index_name} ON {table_name}({', '.join(column_list)})")