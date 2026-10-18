import json

import pytest

from src.db import repository
from src.db.db_repository.notification_status_repository import NotificationStatusRepository
from src.db.db_repository.notifications_queue_repository import NotificationQueueRepository as Queue

@pytest.fixture
def queue():
    repository.register_user_if_not_exists(42)
    group = repository.get_group_by_form_and_year("HR", 2025)
    repository.set_user_group(42, group["id"])
    with repository.get_db_connection() as conn:
        statuses = NotificationStatusRepository.get_status_ids(conn)
        preference = conn.execute(
            "SELECT id FROM notification_preferences WHERE recipient_id = ? LIMIT 1", (42,)
        ).fetchone()["id"]
        conn.execute(
            "UPDATE notification_preferences SET is_enabled = 1 WHERE id = ?", (preference,)
        )
    occurrence = {
        "occurrence_key": "test:1",
        "scheduled_for": 100,
        "expires_at": 1000,
        "group_id": group["id"],
        "target_date": "2026-10-14",
        "payload": {"subject": "Math"},
    }
    with repository.get_db_connection() as conn:
        Queue.reconcile(
            conn, preference_id=preference, occurrences=[occurrence], statuses=statuses, now=90
        )
    return preference, statuses, occurrence


def read_row():
    with repository.get_db_connection() as conn:
        return dict(conn.execute("SELECT * FROM notifications_queue").fetchone())


def claim(statuses, now=100, **kwargs):
    with repository.get_db_connection() as conn:
        return Queue.claim_due(conn, statuses, now=now, **kwargs)


def test_active_lease_prevents_duplicate_claim_and_stale_owner_cannot_complete(queue):
    _, statuses, _ = queue
    first = claim(statuses, lease_seconds=10)[0]
    assert claim(statuses, now=109) == []
    second = claim(statuses, now=110)[0]
    assert first["_claim_token"] != second["_claim_token"]
    with repository.get_db_connection() as conn:
        assert not Queue.mark_delivered(
            conn,
            first["id"],
            first["_claim_token"],
            status_id=statuses["delivered"],
            processing_status_id=statuses["processing"],
            now=111,
        )
        assert not Queue.mark_failed(
            conn,
            first["id"],
            first["_claim_token"],
            statuses=statuses,
            now=111,
            error="stale",
            max_attempts=3,
        )
        assert Queue.mark_delivered(
            conn,
            second["id"],
            second["_claim_token"],
            status_id=statuses["delivered"],
            processing_status_id=statuses["processing"],
            now=111,
        )
    assert read_row()["attempt_count"] == 2
    assert read_row()["claim_token"] is None
    assert claim(statuses, now=112) == []


@pytest.mark.parametrize("restriction", ["future", "expired", "disabled", "banned"])
def test_claim_excludes_ineligible_notifications(queue, restriction):
    preference, statuses, _ = queue
    with repository.get_db_connection() as conn:
        if restriction == "future":
            conn.execute("UPDATE notifications_queue SET next_attempt_at = 101")
        elif restriction == "expired":
            conn.execute("UPDATE notifications_queue SET scheduled_for = 99, expires_at = 100")
        elif restriction == "disabled":
            conn.execute(
                "UPDATE notification_preferences SET is_enabled = 0 WHERE id = ?", (preference,)
            )
        else:
            conn.execute("UPDATE users SET is_banned = 1 WHERE chat_id = 42")
    assert claim(statuses) == []
    assert read_row()["attempt_count"] == 0


def test_retry_backoff_and_attempt_limit(queue):
    _, statuses, _ = queue
    for attempt, now in enumerate([100, 102, 106], start=1):
        item = claim(statuses, now=now)[0]
        with repository.get_db_connection() as conn:
            assert Queue.mark_failed(
                conn,
                item["id"],
                item["_claim_token"],
                statuses=statuses,
                now=now,
                error="x" * 1100,
                max_attempts=3,
            )
        row = read_row()
        assert row["attempt_count"] == attempt
        assert row["claim_token"] is None
        assert row["lease_until"] is None
        assert len(row["last_error"]) == 1000
        assert row["status_id"] == statuses["failed" if attempt == 3 else "pending"]
        assert row["next_attempt_at"] == now + 2**attempt
        assert claim(statuses, now=now + 1) == []
    assert claim(statuses, now=500) == []


def test_reconcile_is_idempotent_and_reactivates_cancelled_occurrence(queue):
    preference, statuses, occurrence = queue
    original_id = read_row()["id"]
    with repository.get_db_connection() as conn:
        for _ in range(2):
            Queue.reconcile(
                conn, preference_id=preference, occurrences=[occurrence], statuses=statuses, now=95
            )
        assert conn.execute("SELECT COUNT(*) FROM notifications_queue").fetchone()[0] == 1
        Queue.reconcile(conn, preference_id=preference, occurrences=[], statuses=statuses, now=96)
    assert read_row()["status_id"] == statuses["cancelled"]
    changed = dict(occurrence, scheduled_for=200, payload={"subject": "Physics"})
    with repository.get_db_connection() as conn:
        Queue.reconcile(
            conn, preference_id=preference, occurrences=[changed], statuses=statuses, now=97
        )
    row = read_row()
    assert row["id"] == original_id
    assert row["status_id"] == statuses["pending"]
    assert row["next_attempt_at"] == 200
    assert json.loads(row["payload_json"]) == changed["payload"]


@pytest.mark.parametrize("status", ["processing", "delivered", "failed", "expired"])
def test_reconcile_preserves_owned_and_terminal_occurrences(queue, status):
    preference, statuses, occurrence = queue
    with repository.get_db_connection() as conn:
        conn.execute("UPDATE notifications_queue SET status_id = ?", (statuses[status],))
    before = read_row()
    with repository.get_db_connection() as conn:
        Queue.reconcile(
            conn,
            preference_id=preference,
            occurrences=[dict(occurrence, scheduled_for=300)],
            statuses=statuses,
            now=200,
        )
    assert read_row() == before