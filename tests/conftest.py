import pytest

from src.db import database, repository
from src.db.migrate import run_migrations


@pytest.fixture(autouse=True)
def initialized_test_database(tmp_path, monkeypatch):
    """Run application tests against the complete current migration state."""
    db_path = tmp_path / "timetable.db"
    run_migrations(db_path)
    database.populate_db(db_path)
    monkeypatch.setattr(repository, "DB_PATH", db_path)
    return db_path
