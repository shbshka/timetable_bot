from src.db import repository as database_repository
from src.db.repository.base import Repository


class NotificationsRepository(Repository):
    """Repository for managing user notification preferences."""

    @property
    def table_name(self) -> str:
        return "notification_preferences"


    @staticmethod
    def get_notification_preferences_by_user_id(user_id: int) -> dict[str, bool]:
        """Fetches notification preferences for a specific user by their ID."""

        with database_repository.get_db_connection() as conn:
            rows = conn.execute(
                """
                SELECT t.name, p.is_enabled
                FROM notification_preferences p
                JOIN notification_types t ON t.id = p.notification_type_id
                WHERE p.recipient_id = ?
                ORDER BY t.id
                """,
                (user_id,)
            ).fetchall()

            return {row["name"]: bool(row["is_enabled"]) for row in rows}


    @staticmethod
    def set_notification_preferences(user_id: int, preferences: dict) -> None:
        """Sets or updates notification preferences for a specific user."""

        with database_repository.get_db_connection() as conn:
            conn.execute(
                """
                INSERT INTO notification_preferences (
                    notification_type_id, recipient_id, is_enabled
                )
                SELECT id, ?, ?
                FROM notification_types
                WHERE name = ?
                ON CONFLICT(recipient_id, notification_type_id)
                DO UPDATE SET is_enabled = excluded.is_enabled
                """,
                (
                    user_id,
                    preferences["is_enabled"],
                    preferences["type"],
                ),
            )
    