import sqlite3
from abc import ABC, abstractmethod

from src.db.database import get_db_connection


class Repository(ABC):

    @property
    @abstractmethod
    def table_name(self) -> str:
        """The name of the table associated with this repository."""


    def get_items(self) -> list[dict]:
        """Fetches all items from the repository."""

        with get_db_connection() as conn:
                rows = conn.execute(f"SELECT * FROM {self.table_name}").fetchall()
                return [dict(row) for row in rows]


    def get_item_by_id(self, item_id: int) -> dict | None:
        """Fetches a single item by its ID from the repository."""

        with get_db_connection() as conn:
                row = conn.execute(f"SELECT * FROM {self.table_name} WHERE id = ?", (item_id,)).fetchone()
                return dict(row) if row else None


    def add_item(self, item_data: dict) -> int:
        """Adds a new item to the repository and returns its ID."""

        with get_db_connection() as conn:
                cursor = conn.cursor()
                columns = ', '.join(item_data.keys())
                placeholders = ', '.join('?' for _ in item_data)
                cursor.execute(
                    f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})",
                    tuple(item_data.values())
                )
                conn.commit()
                return cursor.lastrowid


    def update_item(self, item_id: int, item_data: dict) -> None:
        """Updates an existing item in the repository."""

        with get_db_connection() as conn:
                columns = ', '.join(f"{key} = ?" for key in item_data.keys())
                conn.execute(
                    f"UPDATE {self.table_name} SET {columns} WHERE id = ?",
                    tuple(item_data.values()) + (item_id,)
                )
                conn.commit()


    def delete_item_by_id(self, item_id: int) -> None:
        """Deletes an item from the repository by its ID."""

        with get_db_connection() as conn:
                conn.execute(f"DELETE FROM {self.table_name} WHERE id = ?", (item_id,))
                conn.commit()