import sys

from config import TELEGRAM_BOT_TOKEN
from src.bot.app import create_bot_app
from src.services.health_server import start_health_server
from src.utils.logger import get_logger

logger = get_logger("app")


def main() -> None:
    """Entry point for running the bot application."""
    if not TELEGRAM_BOT_TOKEN:
        logger.critical("TELEGRAM_BOT_TOKEN is missing! Please check your .env file.")
        sys.exit(1)

    logger.info("Starting University Timetable Bot...")

    try:
        logger.info("Initializing health server...")
        health_server = start_health_server()
        logger.info(f"Health server started on {health_server.server_address}")

        app = create_bot_app()
        logger.info("Bot successfully initialized. Starting polling loop...")

        app.run_polling(drop_pending_updates=True)

    except KeyboardInterrupt:
        logger.info("Bot execution interrupted by user (Ctrl+C). Shutting down...")
    except Exception as e:
        logger.critical(f"Fatal error encountered during startup: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if "health_server" in locals():
            health_server.shutdown()
            health_server.server_close()
            logger.info("Health server has been shut down.")

        logger.info("Bot has been shut down.")


if __name__ == "__main__":
    main()