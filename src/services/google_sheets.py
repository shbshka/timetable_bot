import asyncio
import base64
import json
import os
from datetime import UTC, datetime

import httpx
from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials

from config import PROJECT_ROOT
from src.services.snapshots.snapshot_cleanup import cleanup_snapshots_for_sheet
from src.services.snapshots.snapshot_paths import snapshot_directory
from src.utils.logger import get_logger

logger = get_logger("google")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


def _save_schedule_snapshot(
    sheet_id: str,
    sheet_name: str,
    grid: list[list[dict[str, str]]],
    group_name: str | None = None,
) -> None:
    timestamp = datetime.now(UTC)
    snapshots_dir = snapshot_directory(group_name)
    snapshot_path = snapshots_dir / f"{sheet_id}_{timestamp.strftime('%Y%m%dT%H%M%S_%fZ')}.json"
    payload = {
        "fetched_at": timestamp.isoformat(),
        "spreadsheet_id": sheet_id,
        "sheet_name": sheet_name,
        "grid": grid,
    }
    try:
        snapshots_dir.mkdir(parents=True, exist_ok=True)
        with snapshot_path.open("w", encoding="utf-8") as snapshot_file:
            json.dump(payload, snapshot_file, ensure_ascii=False, indent=2)
        logger.info(f"Saved spreadsheet snapshot to {snapshot_path}")
        cleanup_snapshots_for_sheet(sheet_id, snapshots_dir=snapshots_dir)
    except OSError as e:
        logger.error(f"Could not save spreadsheet snapshot: {e}", exc_info=True)


def get_google_credentials() -> Credentials:
    """Load Google service-account credentials for Azure or local development."""
    encoded_creds = os.getenv("SERVICE_ACCOUNT_BASE64")
    if encoded_creds:
        decoded_json = base64.b64decode(encoded_creds).decode("utf-8")
        creds_dict = json.loads(decoded_json)
        logger.info("Loaded Google credentials from SERVICE_ACCOUNT_BASE64.")
        return Credentials.from_service_account_info(creds_dict, scopes=SCOPES)

    credentials_path = PROJECT_ROOT / "credentials.json"
    logger.info("Loaded Google credentials from local credentials.json.")
    return Credentials.from_service_account_file(str(credentials_path), scopes=SCOPES)


def get_access_token() -> str:
    """Create an OAuth access token from the configured Google credentials."""
    creds = get_google_credentials()
    creds.refresh(Request())
    return creds.token


async def fetch_sheet_data_with_sa(
    sheet_id: str,
    sheet_name: str | None = None,
    group_name: str | None = None,
) -> list[list[dict[str, str]]] | None:
    """
    Fetches values and cell notes using Azure base64 or local service-account credentials.

    :return: 2D list of dicts: [{'value': '4', 'note': '18:30-20:00'}, ...]
    """
    try:
        loop = asyncio.get_running_loop()
        token = await loop.run_in_executor(None, get_access_token)
    except Exception as e:
        logger.error(f"Service account authentication error: {e}")
        return None

    url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}"
    params = {
        "includeGridData": "true",
        "fields": "sheets(properties(title),data/rowData/values(formattedValue,note,effectiveFormat/textFormat/strikethrough))",
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

                # Безопасно достаем strikethrough через цепочку get
                is_strikethrough = bool(
                    cell.get("effectiveFormat", {})
                    .get("textFormat", {})
                    .get("strikethrough", False)
                )

                cell_list.append({
                    "value": val,
                    "note": note,
                    "strikethrough": is_strikethrough
                })
            grid.append(cell_list)

        logger.info(f"Parsed grid with {len(grid)} rows from sheet '{sheet_title}'")
        
        _save_schedule_snapshot(sheet_id, sheet_title, grid, group_name=group_name)
        return grid

    except Exception as e:
        logger.error(f"Error fetching sheet with Service Account: {e}", exc_info=True)
        return None