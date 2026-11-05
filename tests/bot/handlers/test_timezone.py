import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.bot.handlers import timezone as timezone_handlers
from src.bot.keyboards.loading import loading_button
from src.bot.keyboards.timezone import timezone_keyboard, timezone_loading_keyboard

CHAT_ID = 1


def _callbacks(markup) -> list[list[str]]:
    return [[button.callback_data for button in row] for row in markup.inline_keyboard]


def _callback_update(data: str) -> SimpleNamespace:
    query = SimpleNamespace(
        data=data,
        message=SimpleNamespace(reply_markup=timezone_keyboard(CHAT_ID)),
        answer=AsyncMock(),
        edit_message_reply_markup=AsyncMock(),
        edit_message_text=AsyncMock(),
    )
    return SimpleNamespace(
        callback_query=query,
        message=None,
        effective_chat=SimpleNamespace(id=CHAT_ID),
        effective_user=SimpleNamespace(id=CHAT_ID),
    )


@pytest.fixture
def handler_dependencies(monkeypatch) -> SimpleNamespace:
    set_user_timezone = MagicMock()
    planner = MagicMock()
    monkeypatch.setattr(timezone_handlers, "set_user_timezone", set_user_timezone)
    monkeypatch.setattr(timezone_handlers, "Planner", planner)
    monkeypatch.setattr(
        timezone_handlers,
        "get_user_schedule_context",
        lambda _chat_id: {"locale": "ru", "group_name": "G1"},
    )
    return SimpleNamespace(set_user_timezone=set_user_timezone, planner=planner)


def test_selecting_timezone_answers_callback_and_restores_keyboard(handler_dependencies) -> None:
    update = _callback_update("tz:Europe/Berlin")
    query = update.callback_query

    asyncio.run(timezone_handlers.handle_timezone_button_callbacks(update, None))

    query.answer.assert_awaited_once()
    handler_dependencies.set_user_timezone.assert_called_once_with(CHAT_ID, "Europe/Berlin")
    final_markup = query.edit_message_text.await_args.kwargs["reply_markup"]
    assert _callbacks(final_markup) == _callbacks(timezone_keyboard(CHAT_ID))


def test_opening_timezone_menu_from_button_answers_callback(handler_dependencies) -> None:
    update = _callback_update("cmd_timezone")

    asyncio.run(timezone_handlers.timezone_command(update, None))

    update.callback_query.answer.assert_awaited_once()


def test_failed_timezone_change_removes_loading_button(handler_dependencies) -> None:
    handler_dependencies.planner.return_value.replan_notifications_for_user.side_effect = (
        RuntimeError("database is locked")
    )
    update = _callback_update("tz:Europe/Berlin")
    query = update.callback_query

    with pytest.raises(RuntimeError):
        asyncio.run(timezone_handlers.handle_timezone_button_callbacks(update, None))

    last_markup = query.edit_message_reply_markup.await_args.args[0]
    assert _callbacks(last_markup) == _callbacks(timezone_keyboard(CHAT_ID))


@pytest.mark.parametrize("timezone", ["Europe/London", "Europe/Berlin"])
def test_loading_keyboard_replaces_only_the_selected_button(timezone: str) -> None:
    markup = timezone_keyboard(CHAT_ID)

    loading = timezone_loading_keyboard(markup, CHAT_ID, timezone)

    expected = [
        [
            loading_button(CHAT_ID).callback_data if callback == f"tz:{timezone}" else callback
            for callback in row
        ]
        for row in _callbacks(markup)
    ]
    assert _callbacks(loading) == expected
