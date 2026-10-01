import re
from pathlib import Path
from typing import Optional

from config import SNAPSHOTS_DIR

_GROUP_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def snapshot_group_name(group_name: Optional[str]) -> str:
    """Return a filesystem-safe directory name for a student group."""
    if not group_name or not group_name.strip():
        return "unassigned"
    normalized = _GROUP_NAME_RE.sub("_", group_name.strip()).strip("._")
    return normalized or "unassigned"


def snapshot_directory(
    group_name: Optional[str] = None,
    snapshots_dir: Path = SNAPSHOTS_DIR,
) -> Path:
    """Return the directory where a group's schedule snapshots belong."""
    if not group_name:
        return snapshots_dir
    return snapshots_dir / snapshot_group_name(group_name)
