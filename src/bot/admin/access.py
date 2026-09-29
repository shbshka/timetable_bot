from telegram import Update
from telegram.ext import ApplicationHandlerStop, ContextTypes

from src.bot.admin.auth import is_admin
from src.db.repository import is_user_banned
from src.utils.messages import get_user_msg


async def block_banned_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Stop all non-admin updates from registered users marked as banned."""
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat or is_admin(user.id) or not is_user_banned(chat.id):
        return

    if update.callback_query:
        await update.callback_query.answer(get_user_msg(chat.id, "admin.banned_access"), show_alert=True)
    elif update.effective_message:
        await update.effective_message.reply_text(get_user_msg(chat.id, "admin.banned_access"))
    raise ApplicationHandlerStop
