from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.db.repository.notifications_repository import NotificationsRepository
from src.utils.messages import get_user_msg

def notification_preferences_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    """Creates an inline keyboard for notification preferences."""
    preferences = NotificationsRepository.get_notification_preferences_by_user_id(chat_id)

    return InlineKeyboardMarkup(
        [
            *[
                [InlineKeyboardButton(get_user_msg(chat_id, f"btns.btn_{pref_type}")),
                InlineKeyboardButton(
                    get_user_msg(chat_id, "btns.btn_enabled" if is_enabled else "btns.btn_disabled"),
                    callback_data=f"cmd_toggle_pref:{pref_type}",
                    )
                ]
                for pref_type, is_enabled in preferences.items()
            ],
            [InlineKeyboardButton(get_user_msg(chat_id, "timezone.current"), callback_data="cmd_timezone")],
            [InlineKeyboardButton(get_user_msg(chat_id, "btns.btn_home"), callback_data="cmd_home")],
        ]
    )
    