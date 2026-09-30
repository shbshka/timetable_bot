from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from src.bot.handlers.group import choose_form_command
from src.bot.handlers.language import language_command
from src.db.repository import get_user_schedule_context, register_user_if_not_exists
from src.utils.logger import get_logger

logger = get_logger("bot")
from src.utils.messages import get_user_msg


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /start command."""
    if not update.effective_chat or not update.effective_user:
        return

    chat_id = update.effective_chat.id
    first_name = update.effective_user.first_name or "Student"

    logger.info(f"Handling /start command for '{first_name}' (Chat ID: {chat_id})")

    register_user_if_not_exists(
        chat_id,
        username=update.effective_user.username,
        first_name=update.effective_user.first_name,
    )
    user_context = get_user_schedule_context(chat_id)

    logger.info(f"Retrieved user context for chat_id {chat_id}: {user_context}")

    if user_context and user_context.get("group_name"):
        welcome_text = get_user_msg(
            chat_id,
            "start.welcome_back", 
            first_name=first_name, 
            group_name=user_context["group_name"]
        )
        keyboard = [
            [
                InlineKeyboardButton(get_user_msg(chat_id, "btns.btn_today"), callback_data="cmd_today"),
                InlineKeyboardButton(get_user_msg(chat_id, "btns.btn_change_group"), callback_data="cmd_change_group"),
            ],
            [InlineKeyboardButton(get_user_msg(chat_id, "btns.btn_language"), callback_data="cmd_language")],
        ]
    else:
        welcome_text = get_user_msg(chat_id, "start.welcome_new", first_name=first_name)
        keyboard = [
            [InlineKeyboardButton(get_user_msg(chat_id, "btns.btn_select_group"), callback_data="start_group_setup")],
            [InlineKeyboardButton(get_user_msg(chat_id, "btns.btn_language"), callback_data="cmd_language")],
        ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
            await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="HTML")
    elif update.callback_query:
            await update.callback_query.edit_message_text(welcome_text, reply_markup=reply_markup, parse_mode="HTML")


async def handle_start_button_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Routes callback query clicks from the /start menu buttons."""
    query = update.callback_query
    await query.answer()

    data = query.data

    #TODO: refactor this stuff (please)
    if data == "cmd_language":
        await language_command(update, context)
    elif data in ("start_group_setup", "cmd_change_group"):
        await choose_form_command(update, context)
    elif data == "cmd_today":
        from src.bot.handlers.schedule import today_command
        await today_command(update, context)
    elif data == "cmd_home":
        await start_command(update, context)


def register_start_handler(app) -> None:
    """Registers handlers for /start command and its inline buttons."""
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(handle_start_button_callbacks, pattern="^(start_group_setup|cmd_change_group|cmd_today|cmd_language|cmd_home)$"))