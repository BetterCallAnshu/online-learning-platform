"""SQLite connection and schema management."""

import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = BASE_DIR / "schema.sql"
DB_PATH = BASE_DIR / "learning_platform.db"


def connect(path=None) -> sqlite3.Connection:
    """Open a connection with row access by column name and FK enforcement."""
    conn = sqlite3.connect(str(path or DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()


def reset(path=None) -> sqlite3.Connection:
    """Delete the database file and rebuild an empty schema."""
    target = Path(path or DB_PATH)
    if target.exists():
        target.unlink()
    conn = connect(target)
    init_schema(conn)
    return conn
