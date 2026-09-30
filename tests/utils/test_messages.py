from src.utils.messages import get_msg


def test_localized_messages_use_html_and_escape_values() -> None:
    # Arrange
    group_name = "A < B"
    sheet_id = "id&value"

    # Act
    usage = get_msg("admin.usage.attach", locale="en")
    escaped = get_msg(
        "admin.sheet.attached",
        locale="en",
        group_name=group_name,
        sheet_id=sheet_id,
    )

    # Assert
    assert "<code>/attach &lt;group&gt; &lt;link_or_ID&gt;</code>" in usage
    assert "A &lt; B" in escaped
    assert "id&amp;value" in escaped