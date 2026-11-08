import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from telegram.ext import CallbackQueryHandler

from src.bot.handlers.help import handle_help_back_button, register_help_handler
from src.bot.handlers.router import handle_text
from src.bot.keyboards.help import help_back, help_keyboard
from src.utils.messages import get_user_msg

CHAT_ID = 1


def _callbacks(markup) -> list[list[str]]:
    return [[button.callback_data for button in row] for row in markup.inline_keyboard]


def test_back_button_returns_to_help_menu() -> None:
    query = SimpleNamespace(answer=AsyncMock(), edit_message_text=AsyncMock())
    update = SimpleNamespace(callback_query=query, effective_chat=SimpleNamespace(id=CHAT_ID))
    context = SimpleNamespace(user_data={"awaiting_message": True})

    asyncio.run(handle_help_back_button(update, context))

    query.answer.assert_awaited_once_with()
    args, kwargs = query.edit_message_text.await_args
    assert args == (get_user_msg(CHAT_ID, "help.show"),)
    assert _callbacks(kwargs["reply_markup"]) == _callbacks(help_keyboard(CHAT_ID))


def test_text_after_back_button_is_not_forwarded_to_admin(monkeypatch) -> None:
    forward = AsyncMock()
    monkeypatch.setattr("src.bot.handlers.help.forward_message_to_admin", forward)
    query = SimpleNamespace(answer=AsyncMock(), edit_message_text=AsyncMock())
    chat = SimpleNamespace(id=CHAT_ID)
    context = SimpleNamespace(user_data={"awaiting_message": True})

    asyncio.run(
        handle_help_back_button(SimpleNamespace(callback_query=query, effective_chat=chat), context)
    )
    asyncio.run(
        handle_text(
            SimpleNamespace(
                message=SimpleNamespace(text="hello", reply_text=AsyncMock()),
                effective_chat=chat,
                effective_user=SimpleNamespace(id=CHAT_ID, username="student"),
            ),
            context,
        )
    )

    forward.assert_not_awaited()


def test_back_button_callback_is_registered() -> None:
    app = MagicMock()

    register_help_handler(app)

    handlers = [call.args[0] for call in app.add_handler.call_args_list]
    callback_handlers = [h for h in handlers if isinstance(h, CallbackQueryHandler)]
    back_callback = _callbacks(help_back(CHAT_ID))[0][0]
    assert any(h.check_update(_callback_query_update(back_callback)) for h in callback_handlers)


def _callback_query_update(data: str):
    from telegram import CallbackQuery, Update, User

    query = CallbackQuery(
        id="1",
        from_user=User(id=CHAT_ID, first_name="Student", is_bot=False),
        chat_instance="1",
        data=data,
    )
    return Update(update_id=1, callback_query=query)
