import sqlite3
from abc import ABC, abstractmethod
from typing import Any

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


    def get_items_by_filters(self, filters: dict[str, Any] | None) -> list[dict]:
        """Fetches items from the repository based on one or multiple filters."""

        query = f"SELECT * FROM {self.table_name}"
        params = []

        if filters:
            conditions = []
            for column, value in filters.items():
                if not column.isidentifier():
                    raise ValueError(f"Invalid column name: {column}")

                if isinstance(value, (list, tuple)):
                    if not value:
                        continue

                    placeholders = ",".join(["?"] * len(value))
                    conditions.append(f"{column} IN ({placeholders})")
                    params.extend(value)
                else:
                    conditions.append(f"{column} = ?")
                    params.append(value)
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)

        with get_db_connection() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
            return [dict(row) for row in rows]


    def get_items_by_conditions(self, conditions: dict[str, Any] | None) -> list[dict]:
        """Fetches items from the repository based on one or multiple conditions."""
        
        query = f"SELECT * FROM {self.table_name}"
        params = []

        if conditions:
            conditions = []
            for column, value in conditions.items():
                if not column.isidentifier():
                    raise ValueError(f"Invalid column name: {column}")
                
                conditions.append(f"{column} = ?")
                params.append(value)
            
            query += " WHERE " + " OR ".join(conditions)

        with get_db_connection() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
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