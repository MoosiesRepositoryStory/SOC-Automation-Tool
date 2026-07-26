"""XDG-aware path resolution. Nothing else should hardcode a data path —
see docs/architecture.md §2 (an AppImage's read-only mount and a later
Windows build both break on a hardcoded path)."""

import os
from pathlib import Path

APP_NAME = "soc-tool"


def data_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / APP_NAME


def db_path() -> Path:
    return data_dir() / "soc.db"
