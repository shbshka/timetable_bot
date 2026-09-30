from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🇬🇧 English", callback_data="set_locale:en")],
            [InlineKeyboardButton("🇷🇺 Русский", callback_data="set_locale:ru")],
        ]
    )
