# src/utils/sheets_parser.py
import re
from typing import Optional


def extract_sheet_id(url_or_id: str) -> Optional[str]:
    """
    Extracts the spreadsheet ID from a full Google Sheets URL,
    or returns the input if it's already a raw ID.
    """
    url_or_id = url_or_id.strip()
    match = re.search(r"/d/([a-zA-Z0-9-_]+)", url_or_id)
    if match:
        return match.group(1)

    if re.match(r"^[a-zA-Z0-9-_]{20,60}$", url_or_id):
        return url_or_id

    return None