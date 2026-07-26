"""Enforces the app -> core -> data dependency rule from CLAUDE.md's
Layering section: core/ and data/ must never import Qt. Not by discipline —
by this test walking the AST of every file in those directories.

First non-vacuous in Task 4, when data/ gained its first real modules.
"""

import ast
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
GUARDED_DIRS = ["core", "data"]
FORBIDDEN_PREFIXES = ("PySide6", "PyQt6", "PyQt5", "PySide2")


def _python_files(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(directory.rglob("*.py"))


def _imported_module_names(file_path: Path) -> set[str]:
    tree = ast.parse(file_path.read_text(), filename=str(file_path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _all_guarded_files() -> list[Path]:
    files: list[Path] = []
    for dirname in GUARDED_DIRS:
        files.extend(_python_files(PROJECT_ROOT / dirname))
    return files


@pytest.mark.parametrize(
    "file_path", _all_guarded_files(), ids=lambda p: str(p.relative_to(PROJECT_ROOT))
)
def test_no_qt_imports_in_core_or_data(file_path):
    imported = _imported_module_names(file_path)
    offending = {name for name in imported if name.startswith(FORBIDDEN_PREFIXES)}
    assert not offending, (
        f"{file_path.relative_to(PROJECT_ROOT)} imports Qt ({offending}) but "
        f"core/ and data/ must never import Qt"
    )


def test_guarded_dirs_actually_have_files_to_check():
    assert len(_all_guarded_files()) > 0, "no files found under core/ or data/ — test would be vacuous"
