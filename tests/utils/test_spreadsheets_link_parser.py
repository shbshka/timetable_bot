from src.utils.spreadsheets_link_parser import extract_sheet_id


def test_sheet_id_parser_accepts_google_url_and_raw_id() -> None:
    # Arrange
    sheet_id = "1Z8dS1DXH6eFRDFoHWiMMWMRh2zDWloK_NFTquvO5w04"
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"

    # Act
    url_result = extract_sheet_id(url)
    raw_result = extract_sheet_id(sheet_id)
    invalid_result = extract_sheet_id("not-a-sheet")

    # Assert
    assert url_result == sheet_id
    assert raw_result == sheet_id
    assert invalid_result is None