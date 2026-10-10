from telegram import Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from src.utils.messages import get_user_msg


async def notification_preferences_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends notification preferences to the user."""

    if update.message:
            await update.message.reply_text("В разработке")
    elif update.callback_query:
            await update.callback_query.answer("В разработке")  # Placeholder for future implementation



def register_notification_preferences_handler(app) -> None:
    """Registers the /notifications command handler [well currently just the callback] into the Application."""
    app.add_handler(CommandHandler("notifications", notification_preferences_command))
    app.add_handler(CallbackQueryHandler(notification_preferences_command, pattern="^cmd_notification_preferences$"))