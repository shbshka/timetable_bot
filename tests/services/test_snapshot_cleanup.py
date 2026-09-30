from src.services.snapshot_cleanup import cleanup_old_schedule_snapshots


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