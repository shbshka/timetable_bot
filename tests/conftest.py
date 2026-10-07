import sqlite3

import pytest

from src.db import database, repository
from src.db.migrations.m001_initial_schema import InitialSchemaMigration


@pytest.fixture(autouse=True)
def legacy_schema_database(tmp_path, monkeypatch):
    """Run application tests against the schema supported by repository.py."""
    db_path = tmp_path / "timetable.db"
    connection = sqlite3.connect(db_path)
    InitialSchemaMigration().upgrade(connection)
    connection.close()
    database.populate_db(db_path)
    monkeypatch.setattr(repository, "DB_PATH", db_path)
    return db_path
