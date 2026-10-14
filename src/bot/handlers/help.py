from telegram import Update
from telegram.ext import CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters

from src.bot.keyboards.help import help_back, help_keyboard
from src.utils.messages import get_user_msg
from src.services.admin_notifier import forward_message_to_admin
from src.utils.logger import get_logger

logger = get_logger("bot")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a help message to the user."""
    help_text = get_user_msg(update.effective_chat.id, "help.show")

    reply_markup = help_keyboard(update.effective_chat.id)

    await update.message.reply_text(help_text, reply_markup=reply_markup, parse_mode="HTML")


async def handle_get_help_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the 'Get Help' button click from the help menu."""
    logger.debug(f"Handling 'Get Help' button callback for user: {update.effective_user.id}")
    chat_id = update.effective_chat.id

    context.user_data["awaiting_message"] = True
    prompt_text = get_user_msg(chat_id, "help.send_message.prompt")
    reply_markup = help_back(chat_id)

    if update.callback_query:
        await update.callback_query.edit_message_text(prompt_text, reply_markup=reply_markup, parse_mode="HTML")
    elif update.effective_message:
        await update.effective_message.reply_text(prompt_text, reply_markup=reply_markup, parse_mode="HTML")


async def handle_incoming_message_submission(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles incoming messages from users who are submitting a message via the help menu."""
    logger.debug(f"Handling incoming message submission from user: {update.effective_user.id}")
    chat_id = update.effective_chat.id

    if context.user_data.get("awaiting_message"):
        user_message = update.message.text
        if not user_message:
            return
        user_group_name = context.user_data.get("user_group_name", "N/A")

        success = await forward_message_to_admin(
            bot=context.bot,
            user_chat_id=chat_id,
            user_username=update.effective_user.username or "N/A",
            user_group_name=user_group_name,
            message_text=user_message
        )

        context.user_data.pop("awaiting_message", None)

        if success:
            confirmation_text = get_user_msg(chat_id, "help.send_message.success")
            await update.message.reply_text(confirmation_text, parse_mode="HTML")
        else:
            error_text = get_user_msg(chat_id, "help.send_message.failure")
            await update.message.reply_text(error_text, parse_mode="HTML")


def register_help_handler(app) -> None:
    """Registers the /help command handler into the Application."""
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(handle_get_help_button, pattern="^cmd_get_help$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_incoming_message_submission))