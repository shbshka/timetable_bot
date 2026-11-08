from telegram import Update
from telegram.ext import CallbackQueryHandler, ContextTypes


async def handle_loading_button_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Answers clicks on loading buttons so the client does not keep waiting for a response."""
    await update.callback_query.answer()


def register_loading_handler(app) -> None:
    """Registers the loading button callback handler into the Application."""
    app.add_handler(CallbackQueryHandler(handle_loading_button_click, pattern="^ignore_loading$"))
