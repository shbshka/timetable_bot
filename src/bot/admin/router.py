from telegram.ext import Application, CallbackQueryHandler, CommandHandler

from src.bot.admin.handlers.sheets import (
    attach_command, 
    detach_command, 
    handle_sheet_approval_callback, 
    handle_sheet_rejection_callback
)
from src.bot.admin.handlers.users import (
    admin_help_command,
    ban_command,
    unban_command,
    users_command,
)


def register_admin_handlers(app: Application) -> None:
    """Registers all admin-related routes and command listeners."""

    app.add_handler(CommandHandler("attach", attach_command))
    app.add_handler(CommandHandler("detach", detach_command))
    app.add_handler(CallbackQueryHandler(handle_sheet_approval_callback, pattern="^approve_sheet:"))
    app.add_handler(CallbackQueryHandler(handle_sheet_rejection_callback, pattern="^reject_sheet:"))
    app.add_handler(CommandHandler("admin", admin_help_command))
    app.add_handler(CommandHandler("users", users_command))
    app.add_handler(CommandHandler("ban", ban_command))
    app.add_handler(CommandHandler("unban", unban_command))