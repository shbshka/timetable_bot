import json
from time import time
from uuid import uuid4

from src.db import repository
from src.db.db_repository.base import Repository


class NotificationQueueRepository(Repository):
    @property
    def table_name(self) -> str:
        return "notifications_queue"

    @staticmethod
    def get_queued_notifications_by_user_id(
        user_id: int,
    ) -> list[dict]:
        with repository.get_db_connection() as conn:
            rows = conn.execute(
                """
                SELECT q.*, t.name AS notification_type, p.recipient_id
                FROM notifications_queue q
                JOIN notification_preferences p ON p.id = q.notification_id
                JOIN notification_types t ON t.id = p.notification_type_id
                WHERE p.recipient_id = ?
                ORDER BY q.created_at, q.id
                """,
                (user_id,),
            ).fetchall()

            return [dict(row) for row in rows]

    @staticmethod
    def claim_due(
        conn,
        statuses: dict[str, int],
        *,
        now: int | None = None,
        lease_seconds: int = 300,
        limit: int = 50,
    ) -> list[dict]:
        """Atomically claim due queue rows and return their delivery data."""
        if lease_seconds < 1 or limit < 1:
            raise ValueError("Lease and batch size must be positive")

        now = int(time()) if now is None else now
        token = uuid4().hex
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                """
                UPDATE notifications_queue
                SET status_id = ?, claim_token = NULL, lease_until = NULL,
                    status_updated_at = ?
                WHERE status_id = ?
                  AND lease_until IS NOT NULL
                  AND lease_until <= ?
                """,
                (statuses["pending"], now, statuses["processing"], now),
            )
            rows = conn.execute(
                """
                SELECT q.*, t.name AS notification_type,
                       p.recipient_id, u.locale, u.timezone, u.is_banned,
                       g.group_name
                FROM notifications_queue q
                JOIN notification_preferences p ON p.id = q.notification_id
                JOIN notification_types t ON t.id = p.notification_type_id
                JOIN users u ON u.chat_id = p.recipient_id
                LEFT JOIN groups g ON g.id = q.group_id
                WHERE q.status_id = ?
                  AND q.next_attempt_at <= ?
                  AND q.expires_at > ?
                  AND p.is_enabled = 1
                  AND u.is_banned = 0
                  AND (q.claim_token IS NULL OR q.lease_until <= ?)
                ORDER BY q.next_attempt_at, q.id
                LIMIT ?
                """,
                (
                    statuses["pending"], now, now, now, limit,
                ),
            ).fetchall()
            claimed = []
            for row in rows:
                updated = conn.execute(
                    """
                    UPDATE notifications_queue
                    SET status_id = ?, attempt_count = attempt_count + 1,
                        claim_token = ?, lease_until = ?,
                        status_updated_at = ?
                    WHERE id = ? AND status_id = ?
                    """,
                    (
                        statuses["processing"], token, now + lease_seconds,
                        now, row["id"], statuses["pending"],
                    ),
                )
                if updated.rowcount:
                    item = dict(row)
                    item["_claim_token"] = token
                    claimed.append(item)
            conn.commit()
            return claimed
        except Exception:
            conn.rollback()
            raise

    @staticmethod
    def mark_delivered(
        conn,
        notification_id: int,
        token: str,
        *,
        status_id: int,
        processing_status_id: int,
        now: int,
    ) -> bool:
        result = conn.execute(
            """
            UPDATE notifications_queue
            SET status_id = ?, claim_token = NULL, lease_until = NULL,
                status_updated_at = ?, delivered_at = ?
            WHERE id = ? AND status_id = ? AND claim_token = ?
            """,
            (
                status_id, now, now, notification_id, processing_status_id, token,
            ),
        )
        return result.rowcount == 1

    @staticmethod
    def mark_failed(
        conn,
        notification_id: int,
        token: str,
        *,
        statuses: dict[str, int],
        now: int,
        error: str,
        max_attempts: int,
    ) -> bool:
        row = conn.execute(
            """
            SELECT attempt_count, expires_at
            FROM notifications_queue
            WHERE id = ? AND status_id = ? AND claim_token = ?
            """,
            (notification_id, statuses["processing"], token),
        ).fetchone()
        if row is None:
            return False

        terminal = row["attempt_count"] >= max_attempts or now >= row["expires_at"]
        status = statuses["failed"] if terminal else statuses["pending"]
        retry_at = now + min(2 ** min(row["attempt_count"], 8), 300)
        result = conn.execute(
            """
            UPDATE notifications_queue
            SET status_id = ?, next_attempt_at = ?, last_error = ?,
                claim_token = NULL, lease_until = NULL, status_updated_at = ?
            WHERE id = ? AND status_id = ? AND claim_token = ?
            """,
            (
                status, retry_at, error[:1000], now,
                notification_id, statuses["processing"], token,
            ),
        )
        return result.rowcount == 1

    @staticmethod
    def expire_pending(conn, statuses: dict, now: int) -> None:
        conn.execute(
            """
            UPDATE notifications_queue
            SET status_id = ?, status_updated_at = ?
            WHERE status_id = ? AND expires_at <= ?
            """,
            (
                statuses["expired"], now,
                statuses["pending"], now,
            ),
        )

    @staticmethod
    def delete_old_terminal(
        conn,
        statuses: dict,
        cutoff: int,
    ) -> int:
        cursor = conn.execute(
            """
            DELETE FROM notifications_queue
            WHERE status_id IN (?, ?, ?, ?)
              AND status_updated_at < ?
              AND expires_at < ?
            """,
            (
                statuses["delivered"],
                statuses["expired"],
                statuses["cancelled"],
                statuses["failed"],
                cutoff,
                cutoff,
            ),
        )
        return cursor.rowcount

    @staticmethod
    def cancel_pending(
        conn,
        preference_id: int,
        statuses: dict,
        now: int,
    ) -> None:
        conn.execute(
            """
            UPDATE notifications_queue
            SET status_id = ?, status_updated_at = ?
            WHERE notification_id = ? AND status_id = ?
            """,
            (
                statuses["cancelled"], now,
                preference_id, statuses["pending"],
            ),
        )

    @staticmethod
    def reconcile(
        conn,
        *,
        preference_id: int,
        occurrences: list[dict],
        statuses: dict,
        now: int,
    ) -> None:
        existing = {
            row["occurrence_key"]: dict(row)
            for row in conn.execute(
                """
                SELECT *
                FROM notifications_queue
                WHERE notification_id = ?
                """,
                (preference_id,),
            ).fetchall()
        }

        desired_keys = {
            item["occurrence_key"] for item in occurrences
        }

        for key, row in existing.items():
            if (
                row["status_id"] == statuses["pending"]
                and key not in desired_keys
            ):
                conn.execute(
                    """
                    UPDATE notifications_queue
                    SET status_id = ?, status_updated_at = ?
                    WHERE id = ?
                    """,
                    (statuses["cancelled"], now, row["id"]),
                )

        for item in occurrences:
            payload = json.dumps(
                item["payload"],
                sort_keys=True,
                ensure_ascii=False,
            )
            row = existing.get(item["occurrence_key"])

            if row is None:
                conn.execute(
                    """
                    INSERT INTO notifications_queue (
                        notification_id, occurrence_key,
                        scheduled_for, expires_at,
                        group_id, target_date, payload_json,
                        status_id, next_attempt_at,
                        created_at, status_updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(notification_id, occurrence_key)
                    DO NOTHING
                    """,
                    (
                        preference_id,
                        item["occurrence_key"],
                        item["scheduled_for"],
                        item["expires_at"],
                        item["group_id"],
                        item["target_date"],
                        payload,
                        statuses["pending"],
                        item["scheduled_for"],
                        now,
                        now,
                    ),
                )
                continue

            if row["status_id"] not in {
                statuses["pending"], statuses["cancelled"],
            }:
                continue

            changed = (
                row["scheduled_for"] != item["scheduled_for"]
                or row["expires_at"] != item["expires_at"]
                or row["group_id"] != item["group_id"]
                or row["target_date"] != item["target_date"]
                or row["payload_json"] != payload
            )
            reactivating = row["status_id"] == statuses["cancelled"]

            if not changed and not reactivating:
                continue

            conn.execute(
                """
                UPDATE notifications_queue
                SET scheduled_for = ?, expires_at = ?,
                    group_id = ?, target_date = ?, payload_json = ?,
                    status_id = ?, next_attempt_at = ?,
                    attempt_count = 0, last_error = NULL,
                    claim_token = NULL, lease_until = NULL,
                    status_updated_at = ?
                WHERE id = ?
                """,
                (
                    item["scheduled_for"],
                    item["expires_at"],
                    item["group_id"],
                    item["target_date"],
                    payload,
                    statuses["pending"],
                    item["scheduled_for"],
                    now,
                    row["id"],
                ),
            )