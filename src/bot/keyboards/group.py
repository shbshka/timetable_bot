from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import YEARS


def form_selection_keyboard(forms: set[str]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(form, callback_data=f"set_form:{form}")] for form in forms]
    )


def year_selection_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(f"Year {year}", callback_data=f"set_year:{year}")] for year in YEARS]
    )
