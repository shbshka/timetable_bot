from telegram import InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from src.bot.handlers.group import choose_form_command
from src.bot.keyboards.home import home_keyboard
from src.db.repository import get_user_schedule_context
from src.utils.logger import get_logger

logger = get_logger("bot")
from src.utils.messages import get_user_msg


async def home_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /home command."""
    if not update.effective_chat or not update.effective_user:
        return

    chat_id = update.effective_chat.id
    first_name = update.effective_user.first_name
    user_context = get_user_schedule_context(chat_id)

    welcome_text = get_user_msg(
        chat_id,
        "start.welcome_back", 
        first_name=first_name, 
        group_name=user_context["group_name"],
        timezone=user_context["timezone"]
    )

    #TODO: refactor this to use a single function for generating the keyboard
    reply_markup = InlineKeyboardMarkup(home_keyboard(chat_id))

    if update.message:
            await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="HTML")
    elif update.callback_query:
            await update.callback_query.edit_message_text(welcome_text, reply_markup=reply_markup, parse_mode="HTML")


async def handle_home_button_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Routes callback query clicks from the /home menu buttons."""
    query = update.callback_query
    await query.answer()

    data = query.data

    #TODO: refactor this stuff (please) match case?
    if data == "cmd_change_group":
        await choose_form_command(update, context)
    elif data == "cmd_today":
        from src.bot.handlers.schedule import today_command
        await today_command(update, context)
    elif data == "cmd_tomorrow":
        from src.bot.handlers.schedule import tomorrow_command
        await tomorrow_command(update, context)
    elif data == "cmd_notification_preferences":
        from src.bot.handlers.notifications import notification_preferences_command
        await notification_preferences_command(update, context)


def register_home_handler(app) -> None:
    """Registers the /home command handler into the Application."""
    app.add_handler(CommandHandler("home", home_command))
    app.add_handler(CallbackQueryHandler(home_command, pattern="^cmd_home$"))
    app.add_handler(CallbackQueryHandler(
         handle_home_button_callbacks, 
         pattern="^(cmd_change_group|cmd_today|cmd_tomorrow|cmd_notification_preferences)$"
         ))