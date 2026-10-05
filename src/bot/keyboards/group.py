from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def form_selection_keyboard(forms: set[str]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(form, callback_data=f"set_form:{form}")] for form in forms]
    )


def year_selection_keyboard(years: set[int]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(f"{year}", callback_data=f"set_year:{year}")] for year in years]
    )

def major_selection_keyboard(majors: set[str]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(major, callback_data=f"set_major:{major}")] for major in majors]
    )