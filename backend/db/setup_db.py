import sqlite3
import os
from pathlib import Path

DB_PATH = os.environ.get("DATABASE_PATH", "./property_intel.db")
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def setup_db():
    schema_sql = SCHEMA_PATH.read_text()
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(schema_sql)
    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")


if __name__ == "__main__":
    setup_db()
