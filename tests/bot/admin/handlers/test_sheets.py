import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, call

import pytest

from src.bot.admin.handlers import sheets


@pytest.mark.parametrize(
    "handler",
    [
        sheets.handle_sheet_approval_callback.__wrapped__,
        sheets.handle_sheet_rejection_callback.__wrapped__,
    ],
)
def test_stale_sheet_submission_shows_localized_alert(handler, monkeypatch) -> None:
    query = SimpleNamespace(
        data="sheet_submission:123",
        answer=AsyncMock(),
        edit_message_text=AsyncMock(),
        message=SimpleNamespace(text="Original message"),
    )
    update = SimpleNamespace(
        callback_query=query,
        effective_user=SimpleNamespace(id=42),
    )
    context = SimpleNamespace()

    monkeypatch.setattr(sheets, "get_pending_submission", lambda submission_id: None)
    monkeypatch.setattr(
        sheets,
        "get_user_msg",
        lambda chat_id, key: "Submission no longer exists.",
    )

    asyncio.run(handler(update, context))

    assert query.answer.await_count == 2
    assert query.answer.await_args_list == [
        call(),
        call("Submission no longer exists.", show_alert=True),
    ]
    query.edit_message_text.assert_not_awaited()
