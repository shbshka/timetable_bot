from src.bot.keyboards.group import form_selection_keyboard, year_selection_keyboard
from src.bot.keyboards.language import language_keyboard
from src.bot.keyboards.start import main_menu_keyboard


def test_group_and_language_keyboards_expose_expected_actions() -> None:
    # Arrange
    forms = {"HR", "LR"}
    years = {1, 2, 3, 4, 5}

    # Act
    form_callbacks = [button.callback_data for row in form_selection_keyboard(forms).inline_keyboard for button in row]
    year_callbacks = [button.callback_data for row in year_selection_keyboard(years).inline_keyboard for button in row]
    language_callbacks = [button.callback_data for row in language_keyboard().inline_keyboard for button in row]

    # Assert
    assert set(form_callbacks) == {"set_form:HR", "set_form:LR"}
    assert "set_year:1" in year_callbacks
    assert "set_year:5" in year_callbacks
    assert language_callbacks == ["set_locale:en", "set_locale:ru"]


def test_start_keyboard_changes_actions_based_on_group_state() -> None:
    # Arrange
    chat_id = 42

    # Act
    grouped = main_menu_keyboard(chat_id, has_group=True)
    ungrouped = main_menu_keyboard(chat_id, has_group=False)
    grouped_callbacks = [button.callback_data for row in grouped.inline_keyboard for button in row]
    ungrouped_callbacks = [button.callback_data for row in ungrouped.inline_keyboard for button in row]

    # Assert
    assert grouped_callbacks == ["cmd_today", "cmd_change_group", "cmd_language"]
    assert ungrouped_callbacks == ["start_group_setup", "cmd_language"]
