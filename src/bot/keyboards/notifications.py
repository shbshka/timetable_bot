from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.db.db_repository.notifications_repository import NotificationPreferencesRepository
from src.utils.messages import get_user_msg


def notification_preferences_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    """Creates an inline keyboard for notification preferences."""
    preferences = NotificationPreferencesRepository.get_notification_preferences_by_user_id(chat_id)

    return InlineKeyboardMarkup(
        [
            *[
                [InlineKeyboardButton(get_user_msg(chat_id, f"notifications.types.{pref_type}"), callback_data=f"unclickable_{pref_type}"),
                InlineKeyboardButton(
                    get_user_msg(chat_id, "btns.btn_enabled" if is_enabled else "btns.btn_disabled"),
                    callback_data=f"cmd_toggle_pref:{pref_type}:{is_enabled}",
                    )
                ]
                for pref_type, is_enabled in preferences.items()
            ],
            [InlineKeyboardButton(get_user_msg(chat_id, "btns.btn_timezone"), callback_data="cmd_timezone")],
            [InlineKeyboardButton(get_user_msg(chat_id, "btns.btn_home"), callback_data="cmd_home")],
        ]
    )


def loading_button(chat_id: int) -> InlineKeyboardButton:
    """Creates an inline loading button."""
    return InlineKeyboardButton(get_user_msg(chat_id, "btns.btn_loading"), callback_data="ignore_loading")


def notification_preferences_loading_keyboard(
    current_markup: InlineKeyboardMarkup,
    chat_id: int,
    pref_type: str,
) -> InlineKeyboardMarkup:
    """Replace the selected preference row with a non-interactive loading button."""
    target_prefix = f"cmd_toggle_pref:{pref_type}:"
    rows = []
    replaced = False

    for row in current_markup.inline_keyboard:
        if any(
            button.callback_data and button.callback_data.startswith(target_prefix)
            for button in row
        ):
            rows.append([loading_button(chat_id)])
            replaced = True
        else:
            rows.append(list(row))

    if not replaced:
        raise ValueError(f"Notification preference row not found: {pref_type}")

    return InlineKeyboardMarkup(rows)