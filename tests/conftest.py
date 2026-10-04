import pytest

from src.db import database, repository


@pytest.fixture(autouse=True)
def initialized_test_database(tmp_path, monkeypatch):
    db_path = tmp_path / "timetable.db"
    database.init_db(db_path)
    database.populate_db(db_path)
    monkeypatch.setattr(repository, "DB_PATH", db_path)
