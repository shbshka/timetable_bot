from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.utils.messages import get_user_msg

def home_keyboard(chat_id: int) -> list[list[InlineKeyboardButton]]:
    keyboard = [
        [
            InlineKeyboardButton(get_user_msg(chat_id, "btns.btn_today"), callback_data="cmd_today"),
            InlineKeyboardButton(get_user_msg(chat_id, "btns.btn_tomorrow"), callback_data="cmd_tomorrow"),
        ],
        [   InlineKeyboardButton(
                get_user_msg(chat_id, "btns.btn_change_group"),
                callback_data="cmd_change_group",
            ),
            InlineKeyboardButton(get_user_msg(chat_id, "btns.btn_notification_preferences"), callback_data="cmd_notification_preferences"),
        ],
        [InlineKeyboardButton(get_user_msg(chat_id, "btns.btn_language"), callback_data="cmd_language")],
    ]
    return keyboard