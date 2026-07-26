"""Task 4 — nav rail position.

For each of the four NavPositions: assert the rail lands in the correct
QGridLayout cell, assert its content widget's layout is structurally the
right type (QVBoxLayout for vertical, QHBoxLayout for horizontal — proof
the rebuild happened, not just a flag flip), and save a real screenshot to
docs/screenshots/nav_<position>.png.

Same headless pattern as tests/theme/test_contrast.py: QT_QPA_PLATFORM=offscreen.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QHBoxLayout, QVBoxLayout

from app.main_window import MainWindow
from app.nav.nav_rail import NavPosition
from app.settings_service import SettingsService
from data.db import connect

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCREENSHOT_DIR = PROJECT_ROOT / "docs" / "screenshots"

EXPECTED_CELL = {
    NavPosition.TOP: (0, 1),
    NavPosition.LEFT: (1, 0),
    NavPosition.RIGHT: (1, 2),
    NavPosition.BOTTOM: (2, 1),
}


@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def window(tmp_path, qapp):
    conn = connect(tmp_path / "test_settings.db")
    service = SettingsService(connection=conn)
    win = MainWindow(settings_service=service)
    win.resize(760, 480)
    yield win
    win.close()


@pytest.mark.parametrize("position", list(NavPosition), ids=lambda p: p.value)
def test_position_sets_correct_grid_cell_and_orientation(window, position, qapp):
    window.set_nav_position(position)
    qapp.processEvents()

    assert window.nav_rail_cell() == EXPECTED_CELL[position], (
        f"{position} landed in {window.nav_rail_cell()}, expected {EXPECTED_CELL[position]}"
    )
    assert window.nav_rail().position() == position

    content_layout = window.nav_rail().content_widget().layout()
    if position.is_vertical:
        assert isinstance(content_layout, QVBoxLayout), (
            f"{position} (vertical) should rebuild a QVBoxLayout content widget, "
            f"got {type(content_layout).__name__}"
        )
    else:
        assert isinstance(content_layout, QHBoxLayout), (
            f"{position} (horizontal) should rebuild a QHBoxLayout content widget, "
            f"got {type(content_layout).__name__}"
        )

    window.show()
    qapp.processEvents()
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = SCREENSHOT_DIR / f"nav_{position.value}.png"
    assert window.grab().save(str(out_path)), f"failed to save screenshot to {out_path}"


def test_position_persists_across_settings_service_instances(tmp_path):
    db_path = tmp_path / "persist.db"

    conn1 = connect(db_path)
    service1 = SettingsService(connection=conn1)
    service1.set_nav_position(NavPosition.BOTTOM)
    conn1.close()

    conn2 = connect(db_path)
    service2 = SettingsService(connection=conn2)
    assert service2.nav_position() == NavPosition.BOTTOM
