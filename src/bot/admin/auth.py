from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes

from config import ADMIN_ID
from src.utils.logger import logger
from src.utils.messages import get_user_msg


def is_admin(user_id: int) -> bool:
    """Checks if a user ID matches the configured admin ID."""
    if isinstance(ADMIN_ID, list):
        return user_id in ADMIN_ID
    return user_id == ADMIN_ID


def admin_only(func):
    """Decorator to restrict admin handler execution to admins only."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user or not is_admin(user.id):
            logger.warning(f"Unauthorized admin access attempt by user {user.id if user else 'Unknown'}")
            if update.callback_query:
                await update.callback_query.answer(get_user_msg(user.id, "admin.unauthorized.callback"), show_alert=True)
            elif update.message:
                await update.message.reply_text(get_user_msg(user.id, "admin.unauthorized.command"))
            return

        return await func(update, context, *args, **kwargs)

    return wrapper