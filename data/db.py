"""SQLite connection + migrations. WAL mode. See docs/architecture.md §2.

Zero Qt imports — core/ and data/ must never import Qt (CLAUDE.md, Layering).
"""

import sqlite3
from pathlib import Path

from data.paths import db_path

SCHEMA_VERSION = 1

_MIGRATIONS = {
    1: """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """,
}


def connect(path: Path | None = None) -> sqlite3.Connection:
    resolved = path or db_path()
    resolved.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(resolved)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    current = conn.execute("PRAGMA user_version;").fetchone()[0]
    for version in range(current + 1, SCHEMA_VERSION + 1):
        conn.executescript(_MIGRATIONS[version])
        conn.execute(f"PRAGMA user_version = {version};")
    conn.commit()
