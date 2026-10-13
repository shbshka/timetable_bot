from telegram import InlineKeyboardButton
from src.utils.messages import get_user_msg


def loading_button(chat_id: int) -> InlineKeyboardButton:
    """Creates an inline loading button."""
    return InlineKeyboardButton(get_user_msg(chat_id, "btns.btn_loading"), callback_data="ignore_loading")
