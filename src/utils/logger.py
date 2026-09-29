import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from config import LOG_LEVEL, ENVIRONMENT

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "bot.log"

def setup_logger(name: str = "timetable_bot") -> logging.Logger:

    """Configures and returns a thread-safe logger instance."""

    logger = logging.getLogger(name)

    numeric_level = getattr(logging, LOG_LEVEL, logging.INFO)
    logger.setLevel(numeric_level)

    if logger.handlers:
        return logger

    if ENVIRONMENT == "prod":
        fmt = "%(asctime)s | %(levelname)-7s | [%(filename)s:%(lineno)d] - %(message)s"
    else:
        fmt = "%(asctime)s | %(levelname)-7s | [%(filename)s:%(funcName)s:%(lineno)d] - %(message)s"

    log_format = logging.Formatter(fmt=fmt, datefmt="%Y-%m-%d %H:%M:%S")

    console_handler = logging.StreamHandler(sys.stdout)

    if ENVIRONMENT == "test":
        console_handler.setLevel(logging.WARNING)
    else:
        console_handler.setLevel(numeric_level)

    console_handler.setFormatter(log_format)
    logger.addHandler(console_handler)

    if ENVIRONMENT != "test":
        log_file = LOG_DIR / f"bot_{ENVIRONMENT}.log"
        file_handler = RotatingFileHandler(
            filename=log_file,
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3 if ENVIRONMENT == "prod" else 1,
            encoding="utf-8"
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(log_format)
        logger.addHandler(file_handler)

    silence_level = logging.WARNING if ENVIRONMENT == "prod" else logging.INFO
    logging.getLogger("googleapiclient").setLevel(silence_level)
    logging.getLogger("urllib3").setLevel(silence_level)
    logging.getLogger("httplib2").setLevel(silence_level)

    return logger

logger = setup_logger()