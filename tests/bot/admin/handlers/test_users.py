import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.bot.admin.handlers import users


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
        monkeypatch.setattr(users, name, value)
    asyncio.run(handler.__wrapped__(update, context))
    return update.effective_message.reply_text


def test_admin_help_sends_localized_help(monkeypatch) -> None:
    update = make_update()
    reply = run_handler(
        users.admin_help_command,
        update,
        [],
        monkeypatch,
        get_user_msg=lambda chat_id, key, **kwargs: f"{key}:{chat_id}",
    )

    reply.assert_awaited_once_with("admin.help:42", parse_mode="HTML")


@pytest.mark.parametrize("args", [[], ["1"], ["x", "HR"], ["0", "HR"], ["1", "bad"]])
def test_users_command_rejects_invalid_arguments(args, monkeypatch) -> None:
    update = make_update()
    reply = run_handler(
        users.users_command,
        update,
        args,
        monkeypatch,
        get_user_msg=lambda chat_id, key, **kwargs: key,
    )

    reply.assert_awaited_once_with("admin.users_usage", parse_mode="HTML")


def test_users_command_reports_missing_group(monkeypatch) -> None:
    update = make_update()
    reply = run_handler(
        users.users_command,
        update,
        ["2", "hr"],
        monkeypatch,
        get_group_by_form_and_year=lambda **kwargs: None,
        get_user_msg=lambda chat_id, key, **kwargs: f"{key}:{kwargs}",
    )

    assert reply.await_args.kwargs["parse_mode"] == "HTML"
    assert reply.await_args.args[0].startswith("admin.group_not_found:")


def test_users_command_reports_empty_group(monkeypatch) -> None:
    update = make_update()
    reply = run_handler(
        users.users_command,
        update,
        ["2", "HR"],
        monkeypatch,
        get_group_by_form_and_year=lambda **kwargs: {"id": 7, "group_name": "24HR"},
        get_users_for_group=lambda group_id: [],
        get_user_msg=lambda chat_id, key, **kwargs: key,
    )

    reply.assert_awaited_once_with("admin.users_empty", parse_mode="HTML")


def test_users_command_formats_banned_users_and_splits_messages(monkeypatch) -> None:
    update = make_update()
    records = [
        {"first_name": "A&B", "username": "student", "chat_id": 1, "is_banned": 1},
    ] + [
        {"first_name": None, "username": f"user{i}", "chat_id": i, "is_banned": 0}
        for i in range(2, 27)
    ]
    reply = run_handler(
        users.users_command,
        update,
        ["2", "HR"],
        monkeypatch,
        get_group_by_form_and_year=lambda **kwargs: {"id": 7, "group_name": "24HR"},
        get_users_for_group=lambda group_id: records,
        get_user_msg=lambda chat_id, key, **kwargs: {
            "admin.users_header": "24HR users ({count})",
            "admin.banned_status": "[BANNED]",
        }.get(key, key),
    )

    assert reply.await_count == 2
    first_message = reply.await_args_list[0].args[0]
    second_message = reply.await_args_list[1].args[0]
    assert "A&amp;B" in first_message
    assert "@student" in first_message
    assert "[BANNED]" in first_message
    assert "user26" in second_message
    assert reply.await_args_list[0].kwargs["parse_mode"] == "HTML"


@pytest.mark.parametrize("handler", [users.ban_command, users.unban_command])
@pytest.mark.parametrize("args", [[], ["abc"], ["0"], ["-42"]])
def test_ban_commands_reject_invalid_chat_ids(handler, args, monkeypatch) -> None:
    update = make_update()
    reply = run_handler(
        handler,
        update,
        args,
        monkeypatch,
        get_user_msg=lambda chat_id, key, **kwargs: key,
    )

    reply.assert_awaited_once_with("admin.ban_usage", parse_mode="HTML")


@pytest.mark.parametrize(
    ("handler", "repository_result", "message_key"),
    [
        (users.ban_command, True, "admin.user_banned"),
        (users.ban_command, False, "admin.user_already_banned"),
        (users.unban_command, True, "admin.user_unbanned"),
        (users.unban_command, False, "admin.user_not_banned"),
    ],
)
def test_ban_commands_report_repository_result(
    handler, repository_result, message_key, monkeypatch
) -> None:
    update = make_update()
    reply = run_handler(
        handler,
        update,
        ["123"],
        monkeypatch,
        set_user_banned=lambda chat_id, value: repository_result,
        get_user_msg=lambda _chat_id, key, **kwargs: f"{key}:{kwargs['chat_id']}",
    )

    reply.assert_awaited_once_with(f"{message_key}:123", parse_mode="HTML")
