import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.bot.jobs import watcher


def test_watcher_continues_after_one_notification_failure(monkeypatch) -> None:
    links = [
        {
            "spreadsheet_db_id": 7,
            "sheet_id": "sheet",
            "last_hash": "old",
            "group_id": 1,
            "group_name": "24HR",
            "study_form": "HR",
        }
    ]
    pending = [
        {"id": 1, "chat_id": 10, "group_name": "24HR"},
        {"id": 2, "chat_id": 20, "group_name": "24HR"},
    ]
    sent = []
    updated_hashes = []

    async def send_message(*, chat_id, **kwargs):
        sent.append(chat_id)
        if chat_id == 10:
            raise RuntimeError("blocked bot")

    monkeypatch.setattr(watcher, "get_active_sheets_for_watcher", lambda: links)
    monkeypatch.setattr(watcher, "fetch_sheet_data_with_sa", AsyncMock(return_value=[["grid"]]))
    monkeypatch.setattr(watcher, "refresh_schedule_cache_from_latest_snapshot", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        watcher,
        "get_schedule_cache_state",
        lambda sheet_id: {"content_hash": "new", "lecture_count": 1},
    )
    monkeypatch.setattr(watcher, "schedule_grid_hash", lambda grid: "new")
    monkeypatch.setattr(watcher, "enqueue_schedule_notifications", lambda **kwargs: None)
    monkeypatch.setattr(watcher, "get_group_subscribers", lambda group_id: [10, 20])
    monkeypatch.setattr(watcher, "get_pending_schedule_notifications", lambda *args: pending)
    monkeypatch.setattr(watcher, "mark_schedule_notification_delivered", lambda notification_id: None)
    monkeypatch.setattr(watcher, "has_pending_schedule_notifications", lambda *args: True)
    monkeypatch.setattr(
        watcher,
        "update_spreadsheet_hash",
        lambda spreadsheet_id, content_hash: updated_hashes.append((spreadsheet_id, content_hash)),
    )
    monkeypatch.setattr(watcher, "get_user_msg", lambda *args, **kwargs: "updated")

    context = SimpleNamespace(bot=SimpleNamespace(send_message=send_message))
    asyncio.run(watcher.check_sheet_updates_job(context))

    assert sent == [10, 20]
    assert updated_hashes == []
