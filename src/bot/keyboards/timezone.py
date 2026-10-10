from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.utils.messages import get_user_msg

#TODO: Add timezone selection buttons for different timezones
def timezone_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    """Creates an inline keyboard for timezone selection."""

    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(get_user_msg(chat_id, "timezone.current"), callback_data="cmd_timezone")],
            [InlineKeyboardButton(get_user_msg(chat_id, "btns.btn_home"), callback_data="cmd_home")],
        ]
    )