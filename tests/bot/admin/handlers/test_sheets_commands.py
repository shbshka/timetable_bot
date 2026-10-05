import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.bot.admin.handlers import sheets


def make_update(chat_id: int = 42):
    message = SimpleNamespace(reply_text=AsyncMock())
    return SimpleNamespace(
        effective_chat=SimpleNamespace(id=chat_id),
        effective_user=SimpleNamespace(id=chat_id),
        effective_message=message,
        message=message,
    )


def run_handler(handler, update, args, monkeypatch, **patches):
    context = SimpleNamespace(args=args)
    for name, value in patches.items():
        monkeypatch.setattr(sheets, name, value)
    asyncio.run(handler.__wrapped__(update, context))
    return update.message.reply_text


def test_attach_requires_group_and_sheet_arguments(monkeypatch) -> None:
    update = make_update()
    reply = run_handler(
        sheets.attach_command,
        update,
        ["HR"],
        monkeypatch,
        get_user_msg=lambda chat_id, key, **kwargs: key,
    )

    reply.assert_awaited_once_with("admin.usage.attach", parse_mode="HTML")


def test_attach_rejects_invalid_sheet_link(monkeypatch) -> None:
    update = make_update()
    reply = run_handler(
        sheets.attach_command,
        update,
        ["24HR", "not-a-sheet"],
        monkeypatch,
        extract_sheet_id=lambda value: None,
        get_user_msg=lambda chat_id, key, **kwargs: key,
    )

    reply.assert_awaited_once_with("admin.sheet.invalid")


def test_attach_reports_missing_group(monkeypatch) -> None:
    update = make_update()
    reply = run_handler(
        sheets.attach_command,
        update,
        ["24HR", "sheet-id"],
        monkeypatch,
        extract_sheet_id=lambda value: "sheet-id",
        get_group_by_name=lambda group: None,
        get_user_msg=lambda chat_id, key, **kwargs: f"{key}:{kwargs['group_name']}",
    )

    reply.assert_awaited_once_with("admin.sheet.errors.group_not_found:24HR", parse_mode="HTML")


@pytest.mark.parametrize("cache_valid", [True, False])
def test_attach_reports_cache_result(cache_valid, monkeypatch) -> None:
    update = make_update()
    reply = run_handler(
        sheets.attach_command,
        update,
        ["24HR", "sheet-id"],
        monkeypatch,
        extract_sheet_id=lambda value: "sheet-id",
        get_group_by_name=lambda group: {"id": 7, "group_name": "24HR", "study_form": "HR"},
        _refresh_sheet_cache=AsyncMock(return_value=cache_valid),
        set_group_spreadsheet=lambda **kwargs: None,
        get_user_msg=lambda chat_id, key, **kwargs: key,
    )

    expected = "admin.sheet.attached" if cache_valid else "admin.sheet.invalid"
    reply.assert_awaited_once_with(expected, parse_mode="HTML")


def test_detach_requires_group_argument(monkeypatch) -> None:
    update = make_update()
    reply = run_handler(
        sheets.detach_command,
        update,
        [],
        monkeypatch,
        get_user_msg=lambda chat_id, key, **kwargs: key,
    )

    reply.assert_awaited_once_with("admin.usage.detach", parse_mode="HTML")


def test_detach_reports_missing_group(monkeypatch) -> None:
    update = make_update()
    reply = run_handler(
        sheets.detach_command,
        update,
        ["missing"],
        monkeypatch,
        get_group_by_name=lambda group: None,
        get_user_msg=lambda chat_id, key, **kwargs: f"{key}:{kwargs['group_name']}",
    )

    reply.assert_awaited_once_with("admin.sheet.errors.group_not_found:MISSING", parse_mode="HTML")


@pytest.mark.parametrize(
    ("removed", "message_key"),
    [(True, "admin.sheet.detached"), (False, "admin.sheet.not_attached")],
)
def test_detach_reports_repository_result(removed, message_key, monkeypatch) -> None:
    update = make_update()
    reply = run_handler(
        sheets.detach_command,
        update,
        ["24hr"],
        monkeypatch,
        get_group_by_name=lambda group: {"id": 7, "group_name": "24HR"},
        detach_group_spreadsheet=lambda group_id: removed,
        get_user_msg=lambda chat_id, key, **kwargs: key,
    )

    reply.assert_awaited_once_with(message_key, parse_mode="HTML")
