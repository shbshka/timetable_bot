from telegram import Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from src.bot.keyboards.language import language_keyboard
from src.bot.keyboards.start import main_menu_keyboard
from src.db.repository import get_user_schedule_context, set_user_locale
from src.utils.logger import get_logger
from src.utils.messages import get_user_msg

logger = get_logger("bot")

LANGUAGE_NAMES = {"en": "English", "ru": "Русский"}


async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat:
        return

    chat_id = update.effective_chat.id
    text = get_user_msg(chat_id, "language.prompt")
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=language_keyboard())
    elif update.effective_message:
        await update.effective_message.reply_text(text, reply_markup=language_keyboard())


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
    logger.info(f"User {chat_id} changed language to {locale}")

    user_context = get_user_schedule_context(chat_id)
    logger.info(f"Retrieved user context for chat_id {chat_id}: {user_context}")

    await query.answer()
    await query.edit_message_text(
        get_user_msg(chat_id, "language.changed", language=LANGUAGE_NAMES[locale]),
        reply_markup=main_menu_keyboard(chat_id, bool(user_context and user_context.get("group_name"))),
    )


def register_language_handler(app) -> None:
    """Registers schedule command and callback handlers into the Application."""
    app.add_handler(CommandHandler("language", language_command))
    app.add_handler(CallbackQueryHandler(language_callback, pattern=r"^set_locale:"))