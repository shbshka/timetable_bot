from src.db import repository
from src.db.db_repository.base import Repository


class NotificationsRepository(Repository):
    """Repository for managing user notification preferences."""

    @property
    def table_name(self) -> str:
        return "notification_preferences"


    @staticmethod
    def get_notification_preferences_by_user_id(user_id: int) -> dict[str, bool]:
        """Fetches notification preferences for a specific user by their ID."""

        with repository.get_db_connection() as conn:
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
    def toggle_notification_preference(user_id: int, pref_type: str) -> None:
        """Toggle one notification preference for the user."""

        with repository.get_db_connection() as conn:
            result = conn.execute(
                """
                UPDATE notification_preferences
                SET is_enabled = CASE is_enabled WHEN 1 THEN 0 ELSE 1 END
                WHERE recipient_id = ?
                  AND notification_type_id = (
                      SELECT id FROM notification_types WHERE name = ?
                  )
                """,
                (user_id, pref_type),
            )
            if result.rowcount != 1:
                raise ValueError(
                    f"Notification preference not found for user {user_id}: {pref_type}"
                )
    