from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from src.db.repository import get_user_locale, set_user_locale
from src.utils.messages import get_user_msg

LANGUAGE_NAMES = {"en": "English", "ru": "Русский"}


def _language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🇬🇧 English", callback_data="set_locale:en")],
            [InlineKeyboardButton("🇷🇺 Русский", callback_data="set_locale:ru")],
        ]
    )


async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat:
        return

    chat_id = update.effective_chat.id
    text = get_user_msg(chat_id, "language.prompt")
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=_language_keyboard())
    elif update.effective_message:
        await update.effective_message.reply_text(text, reply_markup=_language_keyboard())


async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not update.effective_chat:
        return

    locale = query.data.split(":", 1)[1]
    if locale not in LANGUAGE_NAMES:
        await query.answer()
        return

    chat_id = update.effective_chat.id
    set_user_locale(chat_id, locale)
    await query.answer()
    await query.edit_message_text(
        get_user_msg(chat_id, "language.changed", language=LANGUAGE_NAMES[locale])
    )


def register_language_handler(app) -> None:
    """Registers schedule command and callback handlers into the Application."""
    app.add_handler(CommandHandler("language", language_command))
    app.add_handler(CallbackQueryHandler(language_callback, pattern=r"^set_locale:"))