from telegram import InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from src.bot.jobs.notifications.planner import Planner
from src.bot.keyboards.timezone import timezone_keyboard, timezone_loading_keyboard
from src.db.repository import get_user_schedule_context, set_user_timezone
from src.utils.logger import get_logger

logger = get_logger("bot")
from src.utils.messages import get_user_msg


async def timezone_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /timezone command."""
    if not update.effective_chat or not update.effective_user:
        return

    chat_id = update.effective_chat.id
    user_context = get_user_schedule_context(chat_id)

    if not user_context:
        await update.message.reply_text(get_user_msg(chat_id, "error.no_group"))
        return

    reply_markup = timezone_keyboard(chat_id, user_context["locale"])
    reply_text = get_user_msg(chat_id, "timezone.prompt", group_name=user_context["group_name"])

    if update.message:
            await update.message.reply_text(reply_text, reply_markup=reply_markup, parse_mode="HTML")
    elif update.callback_query:
            await update.callback_query.edit_message_text(reply_text, reply_markup=reply_markup, parse_mode="HTML")


async def handle_timezone_button_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Routes callback query clicks from the /timezone menu buttons."""
    query = update.callback_query
    chat_id = update.effective_chat.id
    if not query or not chat_id:
        return

    timezone = query.data.split(":")[1]

    if not timezone:
        raise ValueError("Timezone cannot be empty.")

    try:
        _ = ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        logger.error(f"Failed to create ZoneInfo for {timezone}: {exc}")
        raise ValueError(f"Invalid timezone: {timezone}") from exc

    reply_markup = timezone_loading_keyboard(query.message.reply_markup, chat_id, timezone)

    try:
        await query.edit_message_reply_markup(reply_markup)
    except BadRequest as error:
        if "Message is not modified" not in str(error):
            raise

    set_user_timezone(chat_id, timezone)
    Planner().replan_notifications_for_user(chat_id)

    reply_markup = timezone_keyboard(chat_id, get_user_schedule_context(chat_id)["locale"])
    reply_text = get_user_msg(chat_id, "timezone.updated", timezone=timezone)

    try:
        await query.edit_message_text(reply_text, reply_markup=reply_markup, parse_mode="HTML")
    except BadRequest as error:
        if "Message is not modified" not in str(error):
            raise


async def handle_add_timezone_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the callback for adding a new timezone."""
    query = update.callback_query
    await query.answer()

    chat_id = update.effective_chat.id
    await query.edit_message_text(get_user_msg(chat_id, "error.not_implemented"))


def register_timezone_handler(app) -> None:
    """Registers the /timezone command handler into the Application."""
    app.add_handler(CommandHandler("timezone", timezone_command))
    app.add_handler(CallbackQueryHandler(timezone_command, pattern=r"^cmd_timezone$"))
    app.add_handler(CallbackQueryHandler(handle_add_timezone_callback, pattern=r"^cmd_add_timezone"))
    app.add_handler(CallbackQueryHandler(handle_timezone_button_callbacks, pattern=r"^tz:"))