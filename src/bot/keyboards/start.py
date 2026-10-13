from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.bot.keyboards.home import home_keyboard
from src.utils.messages import get_user_msg


def main_menu_keyboard(chat_id: int, has_group: bool) -> InlineKeyboardMarkup:
    if has_group:
        #TODO: refactor this to dismiss double InlineKeyboardMarkup for convenience
        keyboard = home_keyboard(chat_id)
    else:
        keyboard = [
            [
                InlineKeyboardButton(
                    get_user_msg(chat_id, "btns.btn_select_group"),
                    callback_data="start_group_setup",
                )
            ],
            [InlineKeyboardButton(get_user_msg(chat_id, "btns.btn_language"), callback_data="cmd_language")],
        ]
    return InlineKeyboardMarkup(keyboard)
