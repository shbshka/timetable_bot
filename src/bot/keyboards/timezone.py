from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.utils.messages import get_user_msg

#TODO: localize the timezone names in the keyboard
def timezone_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    """Creates an inline keyboard for timezone selection."""

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("London (GMT/BST)", callback_data="tz_Europe/London"), 
                InlineKeyboardButton("Berlin / Warsaw / Krakow (CET/CEST)", callback_data="tz_Europe/Berlin"),
            ],
            [
                InlineKeyboardButton("Vilnius / Kyiv / Bucharest (EET/EEST)", callback_data="tz_Europe/Vilnius"),
                InlineKeyboardButton("Moscow / St. Petersburg (MSK)", callback_data="tz_Europe/Moscow"),
            ],
            [
                InlineKeyboardButton("Yerevan (AMT)", callback_data="tz_Asia/Yerevan"),
                InlineKeyboardButton("Tbilisi (GET)", callback_data="tz_Asia/Tbilisi"),
            ],
            [
                InlineKeyboardButton("Yekaterinburg (YEKT)", callback_data="tz_Asia/Yekaterinburg"),
                InlineKeyboardButton("Almaty / Tashkent", callback_data="tz_Asia/Almaty"),
            ],
            [InlineKeyboardButton("Click to add your timezone", callback_data="cmd_add_timezone")],
            [InlineKeyboardButton(get_user_msg(chat_id, "btns.btn_home"), callback_data="cmd_home")],
        ]
    )