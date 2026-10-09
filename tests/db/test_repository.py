from datetime import date

import pytest

from src.db import repository
from src.parser.academic_year import academic_start_year, enrollment_year
from src.parser.models import Lecture
from src.utils.time import institution_today


def test_schedule_cache_maps_course_year_to_enrollment_group(
    initialized_test_database,
) -> None:
    # Arrange
    academic_year = academic_start_year(institution_today())
    lecture = Lecture(
        date=date(2026, 10, 5),
        time="08:30-10:00",
        subject="Algorithms",
        course_year=2,
        level="HR",
    )
    with repository.get_db_connection() as connection:
        connection.execute(
            """
            INSERT INTO spreadsheets(sheet_id, academic_starting_year)
            VALUES (?, ?)
            """,
            ("sheet-id", academic_year),
        )

    # Act
    count = repository.replace_schedule_for_sheet(
        sheet_id="sheet-id",
        snapshot_path="snapshot.json",
        content_hash="hash",
        academic_year=academic_year,
        lectures=[lecture],
    )
    state = repository.get_schedule_cache_state("sheet-id")
    with repository.get_db_connection() as connection:
        row = connection.execute(
            "SELECT enrollment_year FROM groups WHERE id = (SELECT group_id FROM lectures WHERE source_id = ?)",
            ("sheet-id",),
        ).fetchone()

    # Assert
    assert count == 1
    assert state["lecture_count"] == 1
    assert row["enrollment_year"] == enrollment_year(2, academic_year)


def test_schedule_cache_registers_a_new_sheet_before_inserting_lectures(
    initialized_test_database,
) -> None:
    academic_year = academic_start_year(institution_today())
    lecture = Lecture(
        date=date(2026, 10, 5),
        time="08:30-10:00",
        subject="Algorithms",
        course_year=2,
        level="HR",
    )

    count = repository.replace_schedule_for_sheet(
        sheet_id="new-sheet-id",
        snapshot_path="snapshot.json",
        content_hash="hash",
        academic_year=academic_year,
        lectures=[lecture],
    )

    assert count == 1
    with repository.get_db_connection() as connection:
        sheet = connection.execute(
            "SELECT academic_starting_year FROM spreadsheets WHERE sheet_id = ?",
            ("new-sheet-id",),
        ).fetchone()
        lecture_row = connection.execute(
            "SELECT source_id FROM lectures WHERE source_id = ?",
            ("new-sheet-id",),
        ).fetchone()

    assert sheet["academic_starting_year"] == academic_year
    assert lecture_row["source_id"] == "new-sheet-id"


def test_schedule_cache_rejects_a_lecture_without_group_level(
    initialized_test_database,
) -> None:
    # Arrange
    lecture = Lecture(
        date=date(2026, 10, 5),
        time="08:30-10:00",
        subject="Algorithms",
        course_year=2,
        level=None,
    )

    # Act
    result = pytest.raises(
        ValueError,
        repository.replace_schedule_for_sheet,
        "sheet-id",
        "snapshot.json",
        "hash",
        2026,
        [lecture],
    )

    # Assert
    assert "Cannot cache 1 of 1 lectures" in str(result.value)


def test_user_profile_preserves_locale_group_and_schedule_context(
    initialized_test_database,
) -> None:
    # Arrange
    repository.register_user_if_not_exists(42, username="student", first_name="Student")
    group = repository.get_group_by_form_and_year("HR", enrollment_year(2))

    # Act
    repository.set_user_locale(42, "en")
    repository.set_user_group(42, group["id"])
    locale = repository.get_user_locale(42)
    user_group = repository.get_user_group(42)
    context = repository.get_user_schedule_context(42)
    invalid_locale = pytest.raises(ValueError, repository.set_user_locale, 42, "de")

    # Assert
    assert locale == "en"
    assert user_group["group_name"] == group["group_name"]
    assert context["study_form"] == "HR"
    assert context["sheet_id"] is None
    assert "Unsupported locale" in str(invalid_locale.value)


def test_group_subscribers_exclude_banned_and_disabled_users() -> None:
    with repository.get_db_connection() as connection:
        connection.executemany(
            """
            INSERT INTO users (chat_id, group_id, is_banned)
            VALUES (?, ?, ?)
            """,
            [(1, 1, 0), (2, 1, 1), (3, 1, 0)],
        )
        connection.executemany(
            """
            INSERT INTO notification_preferences (type, recipient_id, is_enabled)
            VALUES ('schedule_change', ?, ?)
            """,
            [(1, 1), (2, 1), (3, 0)],
        )

    assert repository.get_group_subscribers(1) == [1]


def test_pending_schedule_notifications_are_idempotent_and_track_delivery() -> None:
    repository.register_user_if_not_exists(1)
    repository.register_user_if_not_exists(2)
    repository.enqueue_schedule_notifications("sheet", "hash", 1, "24HR", [1, 2])
    repository.enqueue_schedule_notifications("sheet", "hash", 1, "24HR", [1, 2])

    pending = repository.get_pending_schedule_notifications("sheet", "hash")
    assert [item["chat_id"] for item in pending] == [1, 2]
    assert repository.has_pending_schedule_notifications("sheet", "hash")

    repository.mark_schedule_notification_delivered(pending[0]["id"])

    remaining = repository.get_pending_schedule_notifications("sheet", "hash")
    assert [item["chat_id"] for item in remaining] == [2]
    assert repository.has_pending_schedule_notifications("sheet", "hash")

    repository.mark_schedule_notification_delivered(remaining[0]["id"])
    assert not repository.has_pending_schedule_notifications("sheet", "hash")


def test_pending_notifications_support_multiple_types_for_one_user() -> None:
    repository.register_user_if_not_exists(1)
    repository.enqueue_schedule_notifications("sheet", "hash", 1, "24HR", [1])
    with repository.get_db_connection() as connection:
        connection.execute(
            """
            INSERT INTO notification_preferences (type, recipient_id)
            VALUES (?, ?)
            """,
            ("lecture_reminder", 1),
        )
        preference = connection.execute(
            "SELECT id FROM notification_preferences WHERE type = 'lecture_reminder'"
        ).fetchone()
        connection.execute(
            """
            INSERT INTO notifications_queue(notification_id, scheduled_for, status_id)
            VALUES (?, '2026-10-06 08:25:00', 1)
            """,
            (preference["id"],),
        )

    with repository.get_db_connection() as connection:
        rows = connection.execute(
            """
            SELECT p.type, q.scheduled_for
            FROM notifications_queue q
            JOIN notification_preferences p ON p.id = q.notification_id
            WHERE p.recipient_id = 1
            ORDER BY p.type
            """
        ).fetchall()

    assert [row["type"] for row in rows] == [
        "lecture_reminder",
        "schedule_change:sheet:hash",
    ]
    assert rows[0]["scheduled_for"] == "2026-10-06 08:25:00"