from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.bot.keyboards.loading import loading_button
from src.utils.messages import get_user_msg


def timezone_keyboard(chat_id: int, locale: str = 'ru') -> InlineKeyboardMarkup:
    """Creates an inline keyboard for timezone selection."""

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(get_user_msg(chat_id, "timezone.labels.london"), callback_data="tz:Europe/London"), 
                InlineKeyboardButton(get_user_msg(chat_id, "timezone.labels.berlin"), callback_data="tz:Europe/Berlin"),
            ],
            [
                InlineKeyboardButton(get_user_msg(chat_id, "timezone.labels.vilnius"), callback_data="tz:Europe/Vilnius"),
                InlineKeyboardButton(get_user_msg(chat_id, "timezone.labels.moscow"), callback_data="tz:Europe/Moscow"),
            ],
            [
                InlineKeyboardButton(get_user_msg(chat_id, "timezone.labels.yerevan"), callback_data="tz:Asia/Yerevan"),
                InlineKeyboardButton(get_user_msg(chat_id, "timezone.labels.tbilisi"), callback_data="tz:Asia/Tbilisi"),
            ],
            [
                InlineKeyboardButton(get_user_msg(chat_id, "timezone.labels.yekaterinburg"), callback_data="tz:Asia/Yekaterinburg"),
                InlineKeyboardButton(get_user_msg(chat_id, "timezone.labels.almaty"), callback_data="tz:Asia/Almaty"),
            ],
            [InlineKeyboardButton(get_user_msg(chat_id, "timezone.add"), callback_data="cmd_add_timezone")],
            [InlineKeyboardButton(get_user_msg(chat_id, "btns.btn_home"), callback_data="cmd_home")],
        ]
    )

def timezone_loading_keyboard(
    current_markup: InlineKeyboardMarkup,
    chat_id: int,
    timezone: str,
) -> InlineKeyboardMarkup:
    """Replace the selected timezone row with a non-interactive loading button."""
    target_prefix = f"tz:{timezone}"
    rows = []
    replaced = False

    for row in current_markup.inline_keyboard:
        for button in row:
            buttons = []
            if button.callback_data and button.callback_data.startswith(target_prefix):
                buttons.append(loading_button(chat_id))
                replaced = True
            else:
                buttons.append(button)

        rows.append(buttons)

    if not replaced:
        raise ValueError(f"Timezone button not found: {timezone}")

    return InlineKeyboardMarkup(rows)