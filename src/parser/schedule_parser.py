import hashlib
import json
from datetime import datetime

from config import SNAPSHOTS_DIR, SPREADSHEET_ID
from src.db.repository import (
    get_group_by_id,
    get_schedule_cache_state,
    replace_schedule_for_sheet,
)
from src.db.repository import (
    get_schedule_for_group as read_group_schedule,
)
from src.parser.academic_year import academic_start_year
from src.parser.interface import ParsedSchedule, ScheduleGrid
from src.parser.models import Lecture
from src.parser.registry import parse_with_first_successful_parser
from src.services.google_sheets import fetch_sheet_data_with_sa
from src.services.snapshots.snapshot_paths import snapshot_directory
from src.utils.logger import get_logger
from src.utils.time import institution_now

logger = get_logger("parser")


def _current_academic_year() -> int:
    return academic_start_year()


def schedule_grid_hash(grid: ScheduleGrid) -> str:
    content = json.dumps(grid, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def refresh_schedule_cache_from_latest_snapshot(
    sheet_id: str,
    fallback_level: str | None = None,
    group_name: str | None = None,
) -> bool:
    """Load and persist only the newest local snapshot for a spreadsheet."""
    snapshots_dir = snapshot_directory(group_name)
    snapshots = list(snapshots_dir.glob(f"{sheet_id}_*.json"))
    if not snapshots and group_name:
        snapshots = list(SNAPSHOTS_DIR.glob(f"{sheet_id}_*.json"))
    if not snapshots:
        logger.warning("No schedule snapshots found for spreadsheet '%s'.", sheet_id)
        return False

    snapshot_path = max(snapshots, key=lambda path: path.name)
    try:
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
        grid = payload["grid"]
        content_hash = schedule_grid_hash(grid)
        academic_year = _current_academic_year()

        try:
            parser_name, _, lectures = parse_with_first_successful_parser(grid)
        except ValueError as e:
            logger.error(f"Could not parse schedule snapshot for '{sheet_id}': {e}", exc_info=True)
            return False
        if fallback_level:
            normalized_level = fallback_level.strip().upper()
            lectures = [
                Lecture(**{**lecture.__dict__, "level": lecture.level or normalized_level})
                for lecture in lectures
            ]
        
        cache_state = get_schedule_cache_state(sheet_id)
        if (
            cache_state
            and cache_state["content_hash"] == content_hash
            and cache_state["academic_year"] == academic_year
            and cache_state["lecture_count"] == len(lectures)
        ):
            logger.debug("Schedule cache for spreadsheet '%s' is already current.", sheet_id)
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
    target_date: datetime | None = None,
    fetch_full_week: bool = False,
) -> ParsedSchedule:
    """Read schedule models from SQLite, hydrating from the newest snapshot on a cold cache."""
    cache_state = get_schedule_cache_state(sheet_id)
    if not cache_state or cache_state["academic_year"] != _current_academic_year():
        logger.info("Refreshing cold or stale schedule cache for spreadsheet '%s'.", sheet_id)
        group = get_group_by_id(group_id)
        refresh_schedule_cache_from_latest_snapshot(
            sheet_id,
            fallback_level=group["study_form"] if group else None,
            group_name=group["group_name"] if group else None,
        )
    else:
        logger.debug("Using current schedule cache for spreadsheet '%s'.", sheet_id)
    return read_group_schedule(
        group_id=group_id,
        target_date=target_date or institution_now(),
        fetch_full_week=fetch_full_week,
    )


async def fetch_schedule_grid(
    sheet_id: str | None = None,
    sheet_name: str | None = None,
    group_name: str | None = None,
) -> ScheduleGrid:
    """Fetch a spreadsheet grid using the supplied ID or configured default."""
    resolved_sheet_id = sheet_id or SPREADSHEET_ID
    if not resolved_sheet_id:
        raise ValueError("No spreadsheet ID supplied or configured in SPREADSHEET_ID")

    grid = await fetch_sheet_data_with_sa(
        resolved_sheet_id,
        sheet_name=sheet_name,
        group_name=group_name,
    )
    if grid is None:
        raise RuntimeError(f"Could not fetch spreadsheet '{resolved_sheet_id}'")
    return grid


async def fetch_and_parse_schedule(
    sheet_id: str | None = None,
    target_date: datetime | None = None,
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