from datetime import datetime, timedelta

from src.bot.keyboards.schedule import daily_schedule_keyboard, weekly_schedule_keyboard


def test_daily_keyboard_links_adjacent_days_and_week_view() -> None:
    # Arrange
    target_date = datetime(2026, 9, 30)

    # Act
    keyboard = daily_schedule_keyboard(42, target_date)

    # Assert
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    assert callbacks == [
        "cmd_day:2026-09-29",
        "cmd_today",
        "cmd_day:2026-10-01",
        "cmd_week:2026-09-30",
        "cmd_home",
    ]


def test_weekly_keyboard_links_adjacent_and_current_weeks() -> None:
    # Arrange
    target_date = datetime(2026, 9, 30)
    current_week = datetime.now() - timedelta(days=datetime.now().weekday())

    # Act
    keyboard = weekly_schedule_keyboard(42, target_date)

    # Assert
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    assert callbacks[0] == "cmd_week:2026-09-21"
    assert callbacks[1] == f"cmd_week:{current_week.strftime('%Y-%m-%d')}"
    assert callbacks[2] == "cmd_week:2026-10-05"
    assert callbacks[-2:] == ["cmd_today", "cmd_home"]
