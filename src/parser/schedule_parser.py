from datetime import date, datetime
import hashlib
import json
from pathlib import Path
from typing import Optional

from config import SPREADSHEET_ID, SNAPSHOTS_DIR
from src.db.repository import get_schedule_cache_state, get_schedule_for_group as read_group_schedule, replace_schedule_for_sheet
from src.parser.interface import ParsedSchedule, ScheduleGrid
from src.parser.registry import parse_with_first_successful_parser
from src.services.google_sheets import fetch_sheet_data_with_sa
from src.utils.logger import logger


def _current_academic_year() -> int:
    today = date.today()
    return today.year if today.month >= 8 else today.year - 1


def schedule_grid_hash(grid: ScheduleGrid) -> str:
    content = json.dumps(grid, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def refresh_schedule_cache_from_latest_snapshot(sheet_id: str) -> bool:
    """Load and persist only the newest local snapshot for a spreadsheet."""
    snapshots = list(SNAPSHOTS_DIR.glob(f"{sheet_id}_*.json"))
    if not snapshots:
        return False

    snapshot_path = max(snapshots, key=lambda path: path.name)
    try:
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
        grid = payload["grid"]
        content_hash = schedule_grid_hash(grid)
        academic_year = _current_academic_year()

        try:
            parser_name, parser, lectures = parse_with_first_successful_parser(grid)
        except ValueError as e:
            logger.error(f"Could not parse schedule snapshot for '{sheet_id}': {e}", exc_info=True)
            return False
        
        cache_state = get_schedule_cache_state(sheet_id)
        if (
            cache_state
            and cache_state["content_hash"] == content_hash
            and cache_state["academic_year"] == academic_year
            and cache_state["lecture_count"] == len(lectures)
        ):
            return False

        lecture_count = replace_schedule_for_sheet(
            sheet_id=sheet_id,
            snapshot_path=str(snapshot_path),
            content_hash=content_hash,
            academic_year=academic_year,
            lectures=lectures,
        )
        logger.info(
            f"Loaded {lecture_count} schedule entries from latest snapshot "
            f"for spreadsheet '{sheet_id}' using parser '{parser_name}'."
        )
        return True
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as e:
        logger.error(f"Could not load latest schedule snapshot for '{sheet_id}': {e}", exc_info=True)
        return False


def get_cached_schedule(
    sheet_id: str,
    group_id: int,
    target_date: Optional[datetime] = None,
    fetch_full_week: bool = False,
) -> ParsedSchedule:
    """Read schedule models from SQLite, hydrating from the newest snapshot on a cold cache."""
    cache_state = get_schedule_cache_state(sheet_id)
    if not cache_state or cache_state["academic_year"] != _current_academic_year():
        refresh_schedule_cache_from_latest_snapshot(sheet_id)
    return read_group_schedule(
        group_id=group_id,
        target_date=target_date or datetime.now(),
        fetch_full_week=fetch_full_week,
    )


async def fetch_schedule_grid(
    sheet_id: Optional[str] = None,
    sheet_name: Optional[str] = None,
) -> ScheduleGrid:
    """Fetch a spreadsheet grid using the supplied ID or configured default."""
    resolved_sheet_id = sheet_id or SPREADSHEET_ID
    if not resolved_sheet_id:
        raise ValueError("No spreadsheet ID supplied or configured in SPREADSHEET_ID")

    grid = await fetch_sheet_data_with_sa(resolved_sheet_id, sheet_name=sheet_name)
    if grid is None:
        raise RuntimeError(f"Could not fetch spreadsheet '{resolved_sheet_id}'")
    return grid


async def fetch_and_parse_schedule(
    sheet_id: Optional[str] = None,
    target_date: Optional[datetime] = None,
    fetch_full_week: bool = False,
) -> ParsedSchedule:
    """Fetch schedule cells, then hand them to the layout-specific parser."""
    grid = await fetch_schedule_grid(sheet_id=sheet_id)
    logger.info(f"Fetched {len(grid)} rows from spreadsheet '{sheet_id or SPREADSHEET_ID}'")
    _, parser, _ = parse_with_first_successful_parser(grid)
    return parser.parse(
        grid,
        target_date=target_date,
        fetch_full_week=fetch_full_week,
    )