"""Generic key/value settings storage.

Zero Qt imports — see CLAUDE.md, Layering: core/ and data/ must never
import Qt; the GUI calls into this, never the reverse. Deliberately
generic (plain string key/value) rather than nav-position-specific — the
settings table backs whatever future Settings-toggle features need too,
per docs/architecture.md's `settings` table. Domain typing (e.g. NavPosition)
happens one layer up, in app/settings_service.py.
"""

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class Setting:
    key: str
    value: str


class SettingsRepository:
    def __init__(self, connection: sqlite3.Connection):
        self._conn = connection

    def get(self, key: str, default: str | None = None) -> Setting | None:
        row = self._conn.execute(
            "SELECT key, value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return Setting(key=key, value=default) if default is not None else None
        return Setting(key=row["key"], value=row["value"])

    def set(self, key: str, value: str) -> Setting:
        self._conn.execute(
            """
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
        self._conn.commit()
        return Setting(key=key, value=value)
