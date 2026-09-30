import sys
from config import TELEGRAM_BOT_TOKEN
from src.bot.app import create_bot_app
from src.utils.logger import get_logger

logger = get_logger("app")


def main() -> None:
    """Entry point for running the bot application."""
    if not TELEGRAM_BOT_TOKEN:
        logger.critical("TELEGRAM_BOT_TOKEN is missing! Please check your .env file.")
        sys.exit(1)

    logger.info("Starting University Timetable Bot...")

    try:
        # Build and configure bot application
        app = create_bot_app()

        # Start long-polling loop
        logger.info("Bot successfully initialized. Starting polling loop...")
        app.run_polling(drop_pending_updates=True)

    except KeyboardInterrupt:
        logger.info("Bot execution interrupted by user (Ctrl+C). Shutting down...")
    except Exception as e:
        logger.critical(f"Fatal error encountered during startup: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()