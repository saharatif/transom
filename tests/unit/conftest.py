import os
import sqlite3
import sys

import pytest

# Make `import backend...` work when pytest is run from anywhere.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

SCHEMA_PATH = os.path.join(REPO_ROOT, "backend", "db", "schema.sql")


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """A fresh SQLite DB built from the real schema.sql, wired in via
    DATABASE_PATH so backend.db.queries reads/writes it instead of the
    development database.
    """
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    with open(SCHEMA_PATH) as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
    monkeypatch.setenv("DATABASE_PATH", db_path)
    return db_path
