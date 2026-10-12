from src.db.db_repository.base import Repository


class NotificationStatusRepository(Repository):
    @property
    def table_name(self) -> str:
        return "notification_status"

    @staticmethod
    def get_status_ids(conn) -> dict[str, int]:
        """
        Fetches all notification statuses and their corresponding IDs from the database.
        
        returns: dictionary mapping status names to their corresponding IDs
        
        raises: ValueError if any required statuses are missing.
        """
        rows = conn.execute(
            "SELECT id, status FROM notification_status"
        ).fetchall()

        statuses = {row["status"]: row["id"] for row in rows}
        required = {
            "pending", "processing", "delivered",
            "cancelled", "expired", "failed",
        }

        missing = required - statuses.keys()
        if missing:
            raise ValueError(
                f"Missing notification statuses: {sorted(missing)}"
            )

        return statuses