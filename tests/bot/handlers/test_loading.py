import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.bot.handlers.loading import handle_loading_button_click


def test_clicking_loading_button_answers_callback() -> None:
    query = SimpleNamespace(answer=AsyncMock())

    asyncio.run(handle_loading_button_click(SimpleNamespace(callback_query=query), None))

    query.answer.assert_awaited_once_with()
