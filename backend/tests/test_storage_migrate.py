import sqlite3

import pytest

from backend.storage_migrate import copy_database


def test_copy_database_preserves_source_and_refuses_overwrite(tmp_path):
    source = tmp_path / "previous.sqlite3"
    destination = tmp_path / "shared" / "portfolios.sqlite3"
    with sqlite3.connect(source) as db:
        db.execute("CREATE TABLE portfolios (name TEXT)")
        db.execute("INSERT INTO portfolios VALUES ('Saved')")

    copy_database(source, destination)
    with sqlite3.connect(destination) as db:
        assert db.execute("SELECT name FROM portfolios").fetchall() == [("Saved",)]
    with sqlite3.connect(source) as db:
        assert db.execute("SELECT name FROM portfolios").fetchall() == [("Saved",)]

    with pytest.raises(FileExistsError):
        copy_database(source, destination)
    with sqlite3.connect(destination) as db:
        assert db.execute("SELECT name FROM portfolios").fetchall() == [("Saved",)]
