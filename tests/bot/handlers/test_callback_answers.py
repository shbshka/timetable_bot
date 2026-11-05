import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.bot.handlers.help import handle_get_help_button
from src.bot.handlers import home as home_handlers
from src.bot.handlers.notifications import notification_preferences_command

CHAT_ID = 1


def _callback_update() -> SimpleNamespace:
    query = SimpleNamespace(answer=AsyncMock(), edit_message_text=AsyncMock())
    return SimpleNamespace(
        callback_query=query,
        message=None,
        effective_message=None,
        effective_chat=SimpleNamespace(id=CHAT_ID),
        effective_user=SimpleNamespace(id=CHAT_ID, first_name="Student"),
    )


@pytest.mark.parametrize(
    "handler",
    [home_handlers.home_command, notification_preferences_command, handle_get_help_button],
)
def test_menu_button_handlers_answer_callback(handler, monkeypatch) -> None:
    monkeypatch.setattr(
        home_handlers,
        "get_user_schedule_context",
        lambda _chat_id: {"group_name": "G1", "timezone": "UTC"},
    )
    update = _callback_update()
    context = SimpleNamespace(user_data={})

    asyncio.run(handler(update, context))

    update.callback_query.answer.assert_awaited_once_with()
    update.callback_query.edit_message_text.assert_awaited_once()
