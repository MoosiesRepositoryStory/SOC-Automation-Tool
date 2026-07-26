"""SQLite connection + migrations. WAL mode. See docs/architecture.md §2.

Zero Qt imports — core/ and data/ must never import Qt (CLAUDE.md, Layering).
"""

import sqlite3
from pathlib import Path

from data.paths import db_path

SCHEMA_VERSION = 2

_MIGRATIONS = {
    1: """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """,
    # Task 5a. incidents.* carries no status column on purpose — current
    # status is always derived from the latest row in
    # incident_status_history. See docs/architecture.md §2: overwriting a
    # mutable status column would make false-positive-rate-over-time
    # unrecoverable, and it fails silently (the number would still render).
    2: """
        CREATE TABLE IF NOT EXISTS scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            source_path TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id INTEGER REFERENCES scans(id),
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            category TEXT NOT NULL,
            severity TEXT NOT NULL,
            source TEXT NOT NULL,
            src_ip TEXT,
            dst_ip TEXT,
            description TEXT NOT NULL,
            raw TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS incident_status_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id INTEGER NOT NULL REFERENCES incidents(id),
            status TEXT NOT NULL,
            note TEXT NOT NULL DEFAULT '',
            changed_at TEXT NOT NULL,
            changed_by TEXT NOT NULL,
            prev_status TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_status_history_incident
            ON incident_status_history(incident_id, id);
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
