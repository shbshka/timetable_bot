from src.services.snapshot_cleanup import cleanup_old_schedule_snapshots
from src.services.snapshot_paths import snapshot_directory, snapshot_group_name


def _snapshot_name(sheet_id: str, index: int) -> str:
    return f"{sheet_id}_20260930T120000_{index:06d}Z.json"


def test_snapshot_cleanup_keeps_newest_files_for_each_sheet(tmp_path) -> None:
    # Arrange
    for sheet_id in ("sheet-a", "sheet-b"):
        for index in range(4):
            (tmp_path / _snapshot_name(sheet_id, index)).write_text("{}", encoding="utf-8")
    (tmp_path / "not-a-snapshot.json").write_text("{}", encoding="utf-8")

    # Act
    removed = cleanup_old_schedule_snapshots(tmp_path, max_snapshots=2)

    # Assert
    assert removed == 4
    assert len(list(tmp_path.glob("sheet-a_*.json"))) == 2
    assert len(list(tmp_path.glob("sheet-b_*.json"))) == 2
    assert (tmp_path / "not-a-snapshot.json").exists()


def test_snapshot_cleanup_separates_same_sheet_by_group(tmp_path) -> None:
    # Arrange
    for group_name in ("24 HR", "25 HR"):
        group_dir = snapshot_directory(group_name, tmp_path)
        group_dir.mkdir(parents=True)
        for index in range(3):
            (group_dir / _snapshot_name("shared-sheet", index)).write_text("{}", encoding="utf-8")

    # Act
    removed = cleanup_old_schedule_snapshots(tmp_path, max_snapshots=2)

    # Assert
    assert removed == 2
    assert len(list(snapshot_directory("24 HR", tmp_path).glob("shared-sheet_*.json"))) == 2
    assert len(list(snapshot_directory("25 HR", tmp_path).glob("shared-sheet_*.json"))) == 2


def test_snapshot_group_names_are_safe_directory_names(tmp_path) -> None:
    # Arrange
    group_name = "25/HR: evening"

    # Act
    safe_name = snapshot_group_name(group_name)
    directory = snapshot_directory(group_name, tmp_path)

    # Assert
    assert safe_name == "25_HR_evening"
    assert directory == tmp_path / safe_name