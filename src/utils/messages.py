# src/utils/messages.py
from functools import cache
from html import escape
from pathlib import Path

import yaml

LOCALES_DIR = Path(__file__).resolve().parents[1] / "bot" / "locales"
DEFAULT_LOCALE = "ru"
SUPPORTED_LOCALES = ("en", "ru")


@cache
def _load_messages(locale: str) -> dict:
    if locale not in SUPPORTED_LOCALES:
        locale = DEFAULT_LOCALE
    messages_path = LOCALES_DIR / f"{locale}.yaml"
    if not messages_path.exists():
        raise FileNotFoundError(f"Message file not found at {messages_path}")
    with messages_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _resolve_message(messages: dict, keys: list[str]):
    value = messages
    for part in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def get_msg(key: str, locale: str = DEFAULT_LOCALE, **kwargs) -> str:
    """
    Retrieves a localized message using dot notation, falling back to Russian.
    Injects variables using standard python .format(**kwargs).
    """
    locale = locale if locale in SUPPORTED_LOCALES else DEFAULT_LOCALE
    keys = key.split(".")
    val = _resolve_message(_load_messages(locale), keys)
    if val is None and locale != DEFAULT_LOCALE:
        val = _resolve_message(_load_messages(DEFAULT_LOCALE), keys)
    if val is None:
        return f"[{key}]"

    if not kwargs:
        return str(val)
    safe_kwargs = {
        key: value if key == "week_schedule" else escape(str(value))
        for key, value in kwargs.items()
    }
    return str(val).format(**safe_kwargs)


def get_user_msg(user_id: int, key: str, **kwargs) -> str:
    from src.db.repository import get_user_locale
    return get_msg(key, locale=get_user_locale(user_id), **kwargs)