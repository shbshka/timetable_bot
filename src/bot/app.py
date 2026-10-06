from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    TypeHandler,
)

from config import CHECK_INTERVAL_SECONDS, SNAPSHOT_CLEANUP_INTERVAL_SECONDS, TELEGRAM_BOT_TOKEN
from src.bot.admin.access import block_banned_users
from src.bot.admin.router import register_admin_handlers
from src.bot.handlers.group import register_group_handlers
from src.bot.handlers.help import register_help_handler
from src.bot.handlers.language import register_language_handler
from src.bot.handlers.schedule import register_schedule_handlers
from src.bot.handlers.start import register_start_handler
from src.bot.jobs.watcher import (
    check_sheet_updates_job,
    cleanup_schedule_snapshots_job,
    refresh_schedules_on_startup,
)
from src.db.database import init_db, populate_db
from src.db.migrate import run_migrations
from src.utils.logger import get_logger

logger = get_logger("app")


def create_bot_app() -> Application:
    """
    Application factory that initializes SQLite database,
    registers all Telegram handlers, and schedules background jobs.
    """
    logger.info("Initializing database schema...")

    run_migrations()
    populate_db()


    logger.info("Building Telegram application...")
    app = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(lambda _application: refresh_schedules_on_startup())
        .build()
    )

    logger.info("Registering command handlers and callback query listeners...")
    app.add_handler(TypeHandler(Update, block_banned_users), group=-1)

    register_help_handler(app)
    register_start_handler(app)
    register_language_handler(app)
    register_group_handlers(app)
    register_schedule_handlers(app)
    register_admin_handlers(app)


    if app.job_queue:
        logger.info(f"Scheduling sheet watcher job (Interval: {CHECK_INTERVAL_SECONDS}s)...")
        app.job_queue.run_repeating(
            check_sheet_updates_job,
            interval=CHECK_INTERVAL_SECONDS,
            first=10,
            name="google_sheets_watcher"
        )
        app.job_queue.run_repeating(
            cleanup_schedule_snapshots_job,
            interval=SNAPSHOT_CLEANUP_INTERVAL_SECONDS,
            first=10,
            name="schedule_snapshot_cleanup",
        )
    else:
        logger.warning("JobQueue not enabled. Automatic sheet watcher will not run.")

    return app