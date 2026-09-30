import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from typing import Optional, Dict, List, Any, Iterator

from src.parser.models import DaySchedule, Lecture
from src.parser.academic_year import enrollment_year
from src.utils.logger import logger

from config import DB_PATH, SUPPORTED_USER_LOCALES


@contextmanager
def get_db_connection() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def register_user_if_not_exists(
    chat_id: int, 
    username: Optional[str] = None, 
    first_name: Optional[str] = None
) -> None:
    
    """
    Registers a new user in the database if they don't already exist.
    Updates username and first_name if they are different from existing values.
    """

    with get_db_connection() as conn:
        conn.execute("""
            INSERT INTO users (chat_id, username, first_name)
            VALUES (?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                username = COALESCE(excluded.username, users.username),
                first_name = COALESCE(excluded.first_name, users.first_name)
        """, (chat_id, username, first_name))


def get_user_locale(chat_id: int) -> str:
    with get_db_connection() as conn:
        row = conn.execute("SELECT locale FROM users WHERE chat_id = ?", (chat_id,)).fetchone()
        locale = row["locale"] if row else None
        return locale if locale in SUPPORTED_USER_LOCALES else "ru"


def set_user_locale(chat_id: int, locale: str) -> None:
    if locale not in SUPPORTED_USER_LOCALES:
        raise ValueError(f"Unsupported locale: {locale}")
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO users (chat_id, locale)
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET locale = excluded.locale
            """,
            (chat_id, locale),
        )


def get_user_group(chat_id: int) -> Optional[Dict[str, Any]]:
    """Fetches the group details for a given user."""
    with get_db_connection() as conn:
        row = conn.execute("""
            SELECT g.id, g.group_name, g.study_form, g.enrollment_year
            FROM users u
            JOIN groups g ON u.group_id = g.id
            WHERE u.chat_id = ?
        """, (chat_id,)).fetchone()
        return dict(row) if row else None


def set_user_group(chat_id: int, group_id: int) -> None:
    """Binds a Telegram user directly to a group."""
    with get_db_connection() as conn:
        conn.execute("""
            INSERT INTO users (chat_id, group_id)
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET group_id = excluded.group_id
        """, (chat_id, group_id))


def get_user_schedule_context(chat_id: int) -> Optional[Dict[str, Any]]:
    """
    Fetches user group and active sheet ID
    If only sheet ID is missing, returns values and None for sheet_id
    Returns None if user is not registered or has no group
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                u.chat_id,
                g.id AS group_id,
                g.group_name,
                g.study_form,
                g.enrollment_year,
                s.id AS spreadsheet_db_id,
                s.sheet_id
            FROM users u
            JOIN groups g ON u.group_id = g.id
            LEFT JOIN spreadsheets s ON s.group_id = g.id AND s.is_active = 1
            WHERE u.chat_id = ?
        """, (chat_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_group_by_form_and_year(study_form: str, enrollment_year: int) -> Optional[Dict[str, Any]]:
    """Fetches group ID and details using study_form and enrollment_year."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, group_name, study_form, enrollment_year
            FROM groups 
            WHERE UPPER(study_form) = UPPER(?) AND enrollment_year = ?
        """, (study_form.strip(), enrollment_year))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_group_by_id(group_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a group's study form and enrollment metadata by its database ID."""
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT id, group_name, study_form, enrollment_year FROM groups WHERE id = ?",
            (group_id,),
        ).fetchone()
        return dict(row) if row else None


def get_users_for_group(group_id: int) -> List[Dict[str, Any]]:
    """List registered users and access state for an academic group."""
    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT chat_id, username, first_name, is_banned, created_at
            FROM users
            WHERE group_id = ?
            ORDER BY first_name COLLATE NOCASE, username COLLATE NOCASE, chat_id
            """,
            (group_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def is_user_banned(chat_id: int) -> bool:
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT is_banned FROM users WHERE chat_id = ?",
            (chat_id,),
        ).fetchone()
        return bool(row and row["is_banned"])


def set_user_banned(chat_id: int, banned: bool) -> bool:
    """Set a user's access state; banning an unknown ID creates its record."""
    with get_db_connection() as conn:
        if banned:
            cursor = conn.execute(
                """
                INSERT INTO users (chat_id, is_banned)
                VALUES (?, 1)
                ON CONFLICT(chat_id) DO UPDATE SET is_banned = 1
                WHERE users.is_banned = 0
                """,
                (chat_id,),
            )
        else:
            cursor = conn.execute(
                "UPDATE users SET is_banned = 0 WHERE chat_id = ? AND is_banned = 1",
                (chat_id,),
            )
        return cursor.rowcount > 0


def get_active_sheets_for_watcher() -> List[Dict[str, Any]]:
    """Returns all active spreadsheets and their group details for background polling."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                s.id AS spreadsheet_db_id,
                s.sheet_id,
                s.last_hash,
                g.id AS group_id,
                g.group_name,
                g.study_form
            FROM spreadsheets s
            JOIN groups g ON s.group_id = g.id
            WHERE s.is_active = 1
        """)
        return [dict(row) for row in cursor.fetchall()]


def update_spreadsheet_hash(spreadsheet_db_id: int, new_hash: str) -> None:
    """Updates stored hash of a spreadsheet after detected changes."""
    with get_db_connection() as conn:
        conn.execute("""
            UPDATE spreadsheets 
            SET last_hash = ? 
            WHERE id = ?
        """, (new_hash, spreadsheet_db_id))


def get_schedule_cache_state(sheet_id: str) -> Optional[Dict[str, Any]]:
    """Returns the snapshot version currently represented in the schedule tables."""
    with get_db_connection() as conn:
        row = conn.execute(
            """
            SELECT cache.sheet_id, cache.snapshot_path, cache.content_hash, cache.academic_year,
                   (SELECT COUNT(*) FROM schedule_lectures AS lecture
                    WHERE lecture.sheet_id = cache.sheet_id) AS lecture_count
            FROM schedule_cache AS cache
            WHERE cache.sheet_id = ?
            """,
            (sheet_id,),
        ).fetchone()
        return dict(row) if row else None


def replace_schedule_for_sheet(
    sheet_id: str,
    snapshot_path: str,
    content_hash: str,
    academic_year: int,
    lectures: List[Lecture],
) -> int:
    """Atomically replace a spreadsheet's parsed rows and its cache marker."""
    with get_db_connection() as conn:
        group_ids: Dict[tuple[str, int], Optional[int]] = {}
        rows = []
        unmapped_lectures = []
        for lecture in lectures:
            if lecture.course_year is None or not lecture.level:
                unmapped_lectures.append(lecture)
                continue
            group_enrollment_year = enrollment_year(lecture.course_year, academic_year)
            group_key = (lecture.level.strip().upper(), group_enrollment_year)
            if group_key not in group_ids:
                group = conn.execute(
                    "SELECT id FROM groups WHERE UPPER(study_form) = ? AND enrollment_year = ?",
                    group_key,
                ).fetchone()
                group_ids[group_key] = group["id"] if group else None
            group_id = group_ids[group_key]
            if group_id is None:
                unmapped_lectures.append(lecture)
                continue
            rows.append((
                sheet_id,
                group_id,
                lecture.date.isoformat(),
                lecture.time,
                lecture.subject,
                lecture.room,
                lecture.teacher,
                lecture.form,
                lecture.hours,
                lecture.course_year,
                lecture.level,
                lecture.delivery_mode,
                lecture.course_notes,
                lecture.cell_note,
            ))

        if unmapped_lectures:
            sample = unmapped_lectures[0]
            raise ValueError(
                f"Cannot cache {len(unmapped_lectures)} of {len(lectures)} lectures: "
                f"no group matches course_year={sample.course_year}, level={sample.level!r}."
            )
        if not rows:
            raise ValueError("Cannot cache a schedule with no lecture rows.")

        conn.execute("DELETE FROM schedule_lectures WHERE sheet_id = ?", (sheet_id,))
        conn.executemany(
            """
            INSERT INTO schedule_lectures (
                sheet_id, group_id, lecture_date, time, subject, room, teacher,
                form, hours, course_year, level, delivery_mode, course_notes, cell_note
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.execute(
            """
            INSERT INTO schedule_cache (sheet_id, snapshot_path, content_hash, academic_year, loaded_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(sheet_id) DO UPDATE SET
                snapshot_path = excluded.snapshot_path,
                content_hash = excluded.content_hash,
                academic_year = excluded.academic_year,
                loaded_at = CURRENT_TIMESTAMP
            """,
            (sheet_id, snapshot_path, content_hash, academic_year),
        )
        return len(rows)


def get_schedule_for_group(
    group_id: int,
    target_date: date | datetime,
    fetch_full_week: bool = False,
) -> List[DaySchedule]:
    """Read one day or week of schedule models from SQLite for a selected group."""
    requested_date = target_date.date() if isinstance(target_date, datetime) else target_date
    if fetch_full_week:
        start_date = requested_date - timedelta(days=requested_date.weekday())
        day_count = 7
    else:
        start_date = requested_date
        day_count = 1
    end_date = start_date + timedelta(days=day_count - 1)

    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT lecture_date, time, subject, room, teacher, form, hours,
                   course_year, level, delivery_mode, course_notes, cell_note
            FROM schedule_lectures
            WHERE group_id = ? AND lecture_date BETWEEN ? AND ?
            ORDER BY lecture_date, time, subject
            """,
            (group_id, start_date.isoformat(), end_date.isoformat()),
        ).fetchall()

    lectures_by_date: Dict[date, List[Lecture]] = {}
    for row in rows:
        lecture_date = date.fromisoformat(row["lecture_date"])
        lectures_by_date.setdefault(lecture_date, []).append(
            Lecture(
                date=lecture_date,
                time=row["time"],
                subject=row["subject"],
                room=row["room"],
                teacher=row["teacher"],
                form=row["form"],
                hours=row["hours"],
                course_year=row["course_year"],
                level=row["level"],
                delivery_mode=row["delivery_mode"],
                course_notes=row["course_notes"],
                cell_note=row["cell_note"],
            )
        )

    return [
        DaySchedule(
            date=start_date + timedelta(days=offset),
            lectures=lectures_by_date.get(start_date + timedelta(days=offset), []),
        )
        for offset in range(day_count)
    ]


def get_group_subscribers(group_id: int) -> List[int]:
    """Retrieves chat_ids for all users registered to a given group."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT chat_id FROM users WHERE group_id = ?", (group_id,))
        return [row["chat_id"] for row in cursor.fetchall()]


def get_subscribers_by_file(group_id_or_file_id: int) -> List[int]:
    """
    Fetches chat_ids for all users belonging to the group associated with this group/sheet ID.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT chat_id FROM users 
            WHERE group_id = ? 
               OR group_id = (SELECT group_id FROM spreadsheets WHERE id = ?)
        """, (group_id_or_file_id, group_id_or_file_id))
        return [row["chat_id"] for row in cursor.fetchall()]


def get_group_by_name(group_name: str) -> Optional[Dict[str, Any]]:
    """Retrieves group details by group code/name (case-insensitive)."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, group_name, study_form, enrollment_year
            FROM groups 
            WHERE UPPER(group_name) = UPPER(?)
        """, (group_name.strip(),))
        row = cursor.fetchone()
        return dict(row) if row else None


def set_group_spreadsheet(group_id: int, sheet_id: str) -> None:
    """
    Deactivates/deletes any existing spreadsheet links for the group 
    and inserts the new one as active.
    """
    with get_db_connection() as conn:
        old_sheet_ids = {
            row["sheet_id"]
            for row in conn.execute("SELECT sheet_id FROM spreadsheets WHERE group_id = ?", (group_id,))
        }
        conn.execute("DELETE FROM spreadsheets WHERE group_id = ?", (group_id,))
        conn.execute("""
            INSERT INTO spreadsheets (sheet_id, group_id, is_active, updated_at)
            VALUES (?, ?, 1, CURRENT_TIMESTAMP)
        """, (sheet_id, group_id))

        for old_sheet_id in old_sheet_ids - {sheet_id}:
            conn.execute(
                "DELETE FROM schedule_lectures WHERE group_id = ? AND sheet_id = ?",
                (group_id, old_sheet_id),
            )
            still_linked = conn.execute(
                "SELECT 1 FROM spreadsheets WHERE sheet_id = ? AND is_active = 1 LIMIT 1",
                (old_sheet_id,),
            ).fetchone()
            if not still_linked:
                conn.execute("DELETE FROM schedule_lectures WHERE sheet_id = ?", (old_sheet_id,))
                conn.execute("DELETE FROM schedule_cache WHERE sheet_id = ?", (old_sheet_id,))


def detach_group_spreadsheet(group_id: int) -> bool:
    """Removes all spreadsheet links associated with a group."""
    with get_db_connection() as conn:
        sheet_ids = [
            row["sheet_id"]
            for row in conn.execute("SELECT sheet_id FROM spreadsheets WHERE group_id = ?", (group_id,))
        ]
        cursor = conn.execute("DELETE FROM spreadsheets WHERE group_id = ?", (group_id,))
        for sheet_id in set(sheet_ids):
            conn.execute(
                "DELETE FROM schedule_lectures WHERE group_id = ? AND sheet_id = ?",
                (group_id, sheet_id),
            )
            still_linked = conn.execute(
                "SELECT 1 FROM spreadsheets WHERE sheet_id = ? AND is_active = 1 LIMIT 1",
                (sheet_id,),
            ).fetchone()
            if not still_linked:
                conn.execute("DELETE FROM schedule_lectures WHERE sheet_id = ?", (sheet_id,))
                conn.execute("DELETE FROM schedule_cache WHERE sheet_id = ?", (sheet_id,))
        return cursor.rowcount > 0


def get_pending_submission(submission_id: int) -> Optional[Dict[str, Any]]:
    """Fetches a pending submission by its ID."""
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT * FROM pending_submissions WHERE id = ?",
            (submission_id,),
        ).fetchone()
        return dict(row) if row else None


def create_pending_submission(group_id: int, group_name: str, sheet_id: str, user_chat_id: int) -> int:
    """Creates a new pending submission entry."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO pending_submissions (group_id, group_name, sheet_id, user_chat_id)
            VALUES (?, ?, ?, ?)
            """,
            (group_id, group_name, sheet_id, user_chat_id),
        )
        return cursor.lastrowid

def delete_pending_submission(submission_id: int) -> bool:
    """Deletes a pending submission by its ID."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM pending_submissions WHERE id = ?",
            (submission_id,),
        )
        return cursor.rowcount > 0
        