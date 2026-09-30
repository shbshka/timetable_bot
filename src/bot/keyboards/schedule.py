from datetime import datetime, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.utils.messages import get_user_msg


def daily_schedule_keyboard(chat_id: int, target_date: datetime) -> InlineKeyboardMarkup:
    previous_date = target_date - timedelta(days=1)
    next_date = target_date + timedelta(days=1)
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"⬅️ {previous_date.strftime('%d.%m')}",
                    callback_data=f"cmd_day:{previous_date.strftime('%Y-%m-%d')}",
                ),
                InlineKeyboardButton(
                    get_user_msg(chat_id, "btns.btn_today"),
                    callback_data="cmd_today",
                ),
                InlineKeyboardButton(
                    f"{next_date.strftime('%d.%m')} ➡️",
                    callback_data=f"cmd_day:{next_date.strftime('%Y-%m-%d')}",
                ),
            ],
            [
                InlineKeyboardButton(
                    get_user_msg(chat_id, "btns.btn_week"),
                    callback_data=f"cmd_week:{target_date.strftime('%Y-%m-%d')}",
                )
            ],
            [InlineKeyboardButton(get_user_msg(chat_id, "btns.btn_home"), callback_data="cmd_home")],
        ]
    )


def weekly_schedule_keyboard(chat_id: int, target_date: datetime) -> InlineKeyboardMarkup:
    week_start = target_date - timedelta(days=target_date.weekday())
    previous_week = week_start - timedelta(days=7)
    next_week = week_start + timedelta(days=7)
    current_week = datetime.now() - timedelta(days=datetime.now().weekday())
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"⬅️ {previous_week.strftime('%d.%m')}",
                    callback_data=f"cmd_week:{previous_week.strftime('%Y-%m-%d')}",
                ),
                InlineKeyboardButton(
                    get_user_msg(chat_id, "btns.btn_current_week"),
                    callback_data=f"cmd_week:{current_week.strftime('%Y-%m-%d')}",
                ),
                InlineKeyboardButton(
                    f"{next_week.strftime('%d.%m')} ➡️",
                    callback_data=f"cmd_week:{next_week.strftime('%Y-%m-%d')}",
                ),
            ],
            [InlineKeyboardButton(get_user_msg(chat_id, "btns.btn_today"), callback_data="cmd_today")],
            [InlineKeyboardButton(get_user_msg(chat_id, "btns.btn_home"), callback_data="cmd_home")],
        ]
    )
