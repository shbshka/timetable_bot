from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.utils.messages import get_user_msg


def help_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(get_user_msg(chat_id, "help.get"), callback_data="cmd_get_help")],
    ]

    return InlineKeyboardMarkup(keyboard)


def help_back(chat_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(get_user_msg(chat_id, "btns.btn_back"), callback_data="cmd_help")],
    ]