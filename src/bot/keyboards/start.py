from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.utils.messages import get_user_msg


def main_menu_keyboard(chat_id: int, has_group: bool) -> InlineKeyboardMarkup:
    if has_group:
        keyboard = [
            [
                InlineKeyboardButton(get_user_msg(chat_id, "btns.btn_today"), callback_data="cmd_today"),
                InlineKeyboardButton(
                    get_user_msg(chat_id, "btns.btn_change_group"),
                    callback_data="cmd_change_group",
                ),
            ],
            [InlineKeyboardButton(get_user_msg(chat_id, "btns.btn_language"), callback_data="cmd_language")],
        ]
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
