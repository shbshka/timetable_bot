import json
from datetime import datetime, timezone
from typing import Dict, List, Optional
import httpx
from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials
from config import SERVICE_ACCOUNT_PATH, SNAPSHOTS_DIR
from src.services.snapshot_cleanup import cleanup_snapshots_for_sheet

from src.utils.logger import get_logger

logger = get_logger("google")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


def _save_schedule_snapshot(sheet_id: str, sheet_name: str, grid: List[List[Dict[str, str]]]) -> None:
    timestamp = datetime.now(timezone.utc)
    snapshot_path = SNAPSHOTS_DIR / f"{sheet_id}_{timestamp.strftime('%Y%m%dT%H%M%S_%fZ')}.json"
    payload = {
        "fetched_at": timestamp.isoformat(),
        "spreadsheet_id": sheet_id,
        "sheet_name": sheet_name,
        "grid": grid,
    }
    try:
        SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        with snapshot_path.open("w", encoding="utf-8") as snapshot_file:
            json.dump(payload, snapshot_file, ensure_ascii=False, indent=2)
        logger.info(f"Saved spreadsheet snapshot to {snapshot_path}")
        cleanup_snapshots_for_sheet(sheet_id)
    except OSError as e:
        logger.error(f"Could not save spreadsheet snapshot: {e}", exc_info=True)


def get_access_token() -> str:
    """Reads SERVICE_ACCOUNT_PATH from env and generates an OAuth token."""
    
    creds = Credentials.from_service_account_file(str(SERVICE_ACCOUNT_PATH), scopes=SCOPES)
    creds.refresh(Request())
    return creds.token


async def fetch_sheet_data_with_sa(
    sheet_id: str,
    sheet_name: Optional[str] = None,
) -> Optional[List[List[Dict[str, str]]]]:
    """
    Fetches values + cell notes using the service account configured in SERVICE_ACCOUNT_PATH.

    :return: 2D list of dicts: [{'value': '4', 'note': '18:30-20:00'}, ...]
    """
    try:
        token = get_access_token()
    except Exception as e:
        logger.error(f"Service account authentication error: {e}")
        return None

    url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}"
    params = {
        "includeGridData": "true",
        "fields": "sheets(properties(title),data/rowData/values(formattedValue,note))",
    }
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, params=params, headers=headers)

        if response.status_code != 200:
            logger.error(
                f"Failed to fetch sheet ID '{sheet_id}'. "
                f"Status: {response.status_code}, Response: {response.text}"
            )
            return None

        logger.info(f"Successfully fetched sheet ID '{sheet_id}' with status {response.status_code}")

        data = response.json()
        sheets = data.get("sheets", [])
        if not sheets:
            logger.info(f"No sheets found in spreadsheet '{sheet_id}'")
            return None

        target_sheet = sheets[0]
        if sheet_name:
            for s in sheets:
                if s.get("properties", {}).get("title") == sheet_name:
                    target_sheet = s
                    break

        sheet_title = target_sheet.get("properties", {}).get("title", "")
        row_data = target_sheet.get("data", [{}])[0].get("rowData", [])

        grid = []
        for row in row_data:
            cell_list = []
            for cell in row.get("values", []):
                val = cell.get("formattedValue", "")
                note = cell.get("note", "")
                cell_list.append({"value": val, "note": note})
            grid.append(cell_list)

        logger.info(f"Parsed grid with {len(grid)} rows from sheet '{sheet_title}'")
        
        _save_schedule_snapshot(sheet_id, sheet_title, grid)
        return grid

    except Exception as e:
        logger.error(f"Error fetching sheet with Service Account: {e}", exc_info=True)
        return None