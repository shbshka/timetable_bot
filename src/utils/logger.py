import logging
import sys
from logging.handlers import RotatingFileHandler

from config import ENVIRONMENT, LOG_LEVEL, PROJECT_ROOT

ROOT_LOGGER_NAME = "timetable_bot"
LOG_DIR = PROJECT_ROOT / "logs"
PURPOSE_LOGS = {
    "app": "application.log",
    "bot": "telegram.log",
    "database": "database.log",
    "migrations": "migrations.log",
    "parser": "parser.log",
    "google": "google_sheets.log",
    "admin": "admin.log",
    "jobs": "jobs.log",
}


class PurposeFilter(logging.Filter):
    def __init__(self, purpose: str) -> None:
        super().__init__()
        self.logger_prefix = f"{ROOT_LOGGER_NAME}.{purpose}"

    def filter(self, record: logging.LogRecord) -> bool:
        return record.name == self.logger_prefix or record.name.startswith(f"{self.logger_prefix}.")


def _formatter() -> logging.Formatter:
    if ENVIRONMENT == "prod":
        fmt = "%(asctime)s | %(levelname)-7s | [%(name)s:%(filename)s:%(lineno)d] - %(message)s"
    else:
        fmt = "%(asctime)s | %(levelname)-7s | [%(name)s:%(filename)s:%(funcName)s:%(lineno)d] - %(message)s"
    return logging.Formatter(fmt=fmt, datefmt="%Y-%m-%d %H:%M:%S")

def setup_logger(name: str = "timetable_bot") -> logging.Logger:
    """Configures and returns a thread-safe logger instance."""

    logger = logging.getLogger(name)

    numeric_level = getattr(logging, LOG_LEVEL, logging.INFO)
    logger.setLevel(numeric_level)

    if logger.handlers:
        return logger

    log_format = _formatter()
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger.propagate = False

    console_handler = logging.StreamHandler(sys.stdout)

    if ENVIRONMENT == "test":
        console_handler.setLevel(logging.WARNING)
    else:
        console_handler.setLevel(numeric_level)

    console_handler.setFormatter(log_format)
    logger.addHandler(console_handler)

    if ENVIRONMENT != "test":
        for purpose, filename in PURPOSE_LOGS.items():
            purpose_dir = LOG_DIR / purpose
            purpose_dir.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                filename=purpose_dir / filename,
                maxBytes=5 * 1024 * 1024,
                backupCount=3 if ENVIRONMENT == "prod" else 1,
                encoding="utf-8",
            )
            file_handler.addFilter(PurposeFilter(purpose))
            file_handler.setLevel(numeric_level)
            file_handler.setFormatter(log_format)
            logger.addHandler(file_handler)

        error_dir = LOG_DIR / "errors"
        error_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            filename=error_dir / "errors.log",
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3 if ENVIRONMENT == "prod" else 1,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.ERROR)
        file_handler.setFormatter(log_format)
        logger.addHandler(file_handler)

    silence_level = logging.WARNING if ENVIRONMENT == "prod" else logging.INFO
    logging.getLogger("googleapiclient").setLevel(silence_level)
    logging.getLogger("urllib3").setLevel(silence_level)
    logging.getLogger("httplib2").setLevel(silence_level)

    return logger


def get_logger(purpose: str) -> logging.Logger:
    """Return a child logger routed to the matching purpose log."""
    normalized_purpose = purpose.strip().lower()
    if normalized_purpose not in PURPOSE_LOGS:
        raise ValueError(f"Unknown log purpose: {purpose}")
    return logging.getLogger(f"{ROOT_LOGGER_NAME}.{normalized_purpose}")


logger = setup_logger()