from datetime import date

import pytest

from src.db import database, repository
from src.parser.academic_year import academic_start_year, enrollment_year
from src.parser.models import Lecture


def test_schedule_cache_maps_course_year_to_enrollment_group(tmp_path, monkeypatch) -> None:
    # Arrange
    db_path = tmp_path / "timetable.db"
    database.init_db(db_path)
    database.populate_db(db_path)
    monkeypatch.setattr(repository, "DB_PATH", db_path)
    academic_year = academic_start_year(date.today())
    lecture = Lecture(
        date=date(2026, 10, 5),
        time="08:30-10:00",
        subject="Algorithms",
        course_year=2,
        level="HR",
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
            "SELECT enrollment_year FROM groups WHERE id = (SELECT group_id FROM schedule_lectures WHERE sheet_id = ?)",
            ("sheet-id",),
        ).fetchone()

    # Assert
    assert count == 1
    assert state["lecture_count"] == 1
    assert row["enrollment_year"] == enrollment_year(2, academic_year)


def test_schedule_cache_rejects_a_lecture_without_group_level(tmp_path, monkeypatch) -> None:
    # Arrange
    db_path = tmp_path / "timetable.db"
    database.init_db(db_path)
    database.populate_db(db_path)
    monkeypatch.setattr(repository, "DB_PATH", db_path)
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


def test_user_profile_preserves_locale_group_and_schedule_context(tmp_path, monkeypatch) -> None:
    # Arrange
    db_path = tmp_path / "timetable.db"
    database.init_db(db_path)
    database.populate_db(db_path)
    monkeypatch.setattr(repository, "DB_PATH", db_path)
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
            INSERT INTO users (chat_id, group_id, is_banned, notifications_enabled)
            VALUES (?, ?, ?, ?)
            """,
            [(1, 1, 0, 1), (2, 1, 1, 1), (3, 1, 0, 0)],
        )

    assert repository.get_group_subscribers(1) == [1]


def test_pending_schedule_notifications_are_idempotent_and_track_delivery() -> None:
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
    repository.enqueue_schedule_notifications("sheet", "hash", 1, "24HR", [1])
    with repository.get_db_connection() as connection:
        connection.execute(
            """
            INSERT INTO pending_notifications (
                notification_type, notification_key, sheet_id, content_hash,
                group_id, group_name, chat_id, scheduled_for
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "lecture_reminder",
                "lecture:42:2026-10-06T08:30",
                "sheet",
                "hash",
                1,
                "24HR",
                1,
                "2026-10-06 08:25:00",
            ),
        )

    with repository.get_db_connection() as connection:
        rows = connection.execute(
            """
            SELECT notification_type, notification_key, scheduled_for
            FROM pending_notifications
            WHERE chat_id = 1
            ORDER BY notification_type
            """
        ).fetchall()

    assert [(row["notification_type"], row["notification_key"]) for row in rows] == [
        ("lecture_reminder", "lecture:42:2026-10-06T08:30"),
        ("schedule_change", "hash"),
    ]
    assert rows[0]["scheduled_for"] == "2026-10-06 08:25:00"