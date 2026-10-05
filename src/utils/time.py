from datetime import date, datetime

from config import INSTITUTION_TIMEZONE


def institution_now() -> datetime:
    """Return the current time in the configured institution timezone."""
    return datetime.now(INSTITUTION_TIMEZONE)


def institution_today() -> date:
    """Return today's date in the configured institution timezone."""
    return institution_now().date()
