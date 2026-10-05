from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from src.utils.messages import get_user_msg


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a help message to the user."""
    help_text = get_user_msg(update.effective_chat.id, "help")
    await update.message.reply_text(help_text)


def register_help_handler(app) -> None:
    """Registers the /help command handler into the Application."""
    app.add_handler(CommandHandler("help", help_command))