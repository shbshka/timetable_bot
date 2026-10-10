from telegram import Update
from telegram.error import BadRequest
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from src.bot.keyboards.notifications import (
    notification_preferences_keyboard,
    notification_preferences_loading_keyboard,
)
from src.db.db_repository.notifications_repository import NotificationsRepository
from src.db.repository import get_user_group_and_tz
from src.utils.logger import get_logger
from src.utils.messages import get_user_msg

logger = get_logger("bot")

async def notification_preferences_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends notification preferences to the user."""

    if not update.effective_chat or not update.effective_user:
        return

    chat_id = update.effective_chat.id

    user_context = get_user_group_and_tz(chat_id)
    group_name = user_context["group_name"] if user_context else "N/A"
    timezone = user_context["timezone"] if user_context else "N/A"

    reply_markup = notification_preferences_keyboard(chat_id)
    reply_text = get_user_msg(chat_id, "notifications.prompt", group_name=group_name, timezone=timezone)

    if update.message:
        await update.message.reply_text(reply_text, reply_markup=reply_markup, parse_mode="HTML")
    elif update.callback_query:
        try:
            await update.callback_query.edit_message_text(
                reply_text,
                reply_markup=reply_markup,
                parse_mode="HTML")
        except BadRequest as e:
            if "Message is not modified" in str(e):
                await update.callback_query.edit_message_reply_markup(
                    reply_markup=reply_markup)
            else:
                logger.error(f"Failed to edit message for chat_id {chat_id}: {e}")


async def toggle_notification_preference(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Toggles a specific notification preference for the user."""
    query = update.callback_query
    await query.answer()

    chat_id = update.effective_chat.id
    pref_type = query.data.split(":")[1]

    if not query.message or not query.message.reply_markup:
        raise ValueError("Notification preference message has no reply markup")

    loading_markup = notification_preferences_loading_keyboard(
        query.message.reply_markup,
        chat_id,
        pref_type,
    )
    try:
        await query.edit_message_reply_markup(reply_markup=loading_markup)
    except BadRequest as error:
        if "Message is not modified" not in str(error):
            raise

    NotificationsRepository.toggle_notification_preference(chat_id, pref_type)

    reply_markup = notification_preferences_keyboard(chat_id)
    try:
        await query.edit_message_reply_markup(reply_markup=reply_markup)
    except BadRequest as error:
        if "Message is not modified" not in str(error):
            raise


def register_notification_preferences_handler(app) -> None:
    """Registers the /notifications command handler into the Application."""
    app.add_handler(CommandHandler("notifications", notification_preferences_command))
    app.add_handler(CallbackQueryHandler(notification_preferences_command, pattern="^cmd_notification_preferences$"))
    app.add_handler(CallbackQueryHandler(toggle_notification_preference, pattern="^cmd_toggle_pref:"))