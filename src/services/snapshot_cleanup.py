import re
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from config import MAX_SCHEDULE_SNAPSHOTS, SNAPSHOTS_DIR
from src.utils.logger import get_logger

logger = get_logger("jobs")

_SNAPSHOT_NAME_RE = re.compile(r"^(?P<sheet_id>.+)_(?P<timestamp>\d{8}T\d{6}_\d{6}Z)\.json$")


def _remove_oldest(snapshots: Iterable[Path], max_snapshots: int) -> int:
    if max_snapshots < 1:
        raise ValueError("max_snapshots must be at least 1")

    ordered = sorted(snapshots, key=lambda path: path.name, reverse=True)
    removed = 0
    for snapshot in ordered[max_snapshots:]:
        try:
            snapshot.unlink()
            removed += 1
        except OSError:
            logger.warning("Could not remove old schedule snapshot '%s'.", snapshot, exc_info=True)
    return removed


def cleanup_snapshots_for_sheet(
    sheet_id: str,
    snapshots_dir: Path = SNAPSHOTS_DIR,
    max_snapshots: int = MAX_SCHEDULE_SNAPSHOTS,
) -> int:
    """Keep only the newest configured number of snapshots for one sheet."""
    if not snapshots_dir.is_dir():
        return 0
    snapshots = [
        path
        for path in snapshots_dir.glob(f"{sheet_id}_*.json")
        if path.is_file() and _SNAPSHOT_NAME_RE.fullmatch(path.name)
    ]
    removed = _remove_oldest(snapshots, max_snapshots)
    if removed:
        logger.info("Removed %d old snapshots for spreadsheet '%s'.", removed, sheet_id)
    return removed


def cleanup_old_schedule_snapshots(
    snapshots_dir: Path = SNAPSHOTS_DIR,
    max_snapshots: int = MAX_SCHEDULE_SNAPSHOTS,
) -> int:
    """Retain the newest snapshots per spreadsheet and remove older files."""
    if max_snapshots < 1:
        raise ValueError("max_snapshots must be at least 1")
    if not snapshots_dir.is_dir():
        return 0

    snapshots_by_group_and_sheet = defaultdict(list)
    for path in snapshots_dir.rglob("*.json"):
        match = _SNAPSHOT_NAME_RE.fullmatch(path.name)
        if path.is_file() and match:
            key = (path.parent, match.group("sheet_id"))
            snapshots_by_group_and_sheet[key].append(path)

    return sum(
        _remove_oldest(snapshots, max_snapshots)
        for snapshots in snapshots_by_group_and_sheet.values()
    )
