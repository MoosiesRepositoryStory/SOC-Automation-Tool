"""Main window shell: QGridLayout, content fixed at (1,1), nav rail
re-parented into whichever surrounding cell matches the current setting.
See docs/architecture.md §4.

Position change = grid.removeWidget + rail.set_orientation() + re-add.
No window teardown, no animation — see app/nav/nav_rail.py docstring for
why animating this specific transition is the constraint to not relearn.
"""

from PySide6.QtWidgets import QGridLayout, QLabel, QMainWindow, QStackedWidget, QWidget

from app.nav.nav_rail import NavItem, NavPosition, NavRail
from app.resources import app_icon
from app.settings_service import SettingsService

APP_NAME = "SOC Automation Tool"

_GRID_CELL = {
    NavPosition.TOP: (0, 1),
    NavPosition.LEFT: (1, 0),
    NavPosition.RIGHT: (1, 2),
    NavPosition.BOTTOM: (2, 1),
}

_DEFAULT_ITEMS = [
    NavItem("dashboard", "Dashboard"),
    NavItem("incidents", "Incidents"),
    NavItem("scans", "Scans"),
    NavItem("settings", "Settings"),
]


class MainWindow(QMainWindow):
    def __init__(
        self,
        settings_service: SettingsService,
        items: list[NavItem] | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.resize(900, 600)

        self._settings = settings_service
        self._items = items if items is not None else _DEFAULT_ITEMS

        central = QWidget()
        self._grid = QGridLayout(central)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(0)

        self._content = QStackedWidget()
        self._content.addWidget(self._placeholder_page())
        self._grid.addWidget(self._content, 1, 1)

        self._rail = NavRail(self._items, position=self._settings.nav_position())
        self._place_rail(self._rail.position())

        self.setCentralWidget(central)

        self._settings.nav_position_changed.connect(self._on_nav_position_changed)

    def content(self) -> QStackedWidget:
        return self._content

    def nav_rail(self) -> NavRail:
        return self._rail

    def nav_rail_cell(self) -> tuple[int, int]:
        index = self._grid.indexOf(self._rail)
        row, col, _row_span, _col_span = self._grid.getItemPosition(index)
        return (row, col)

    def set_nav_position(self, position: NavPosition) -> None:
        self._settings.set_nav_position(position)

    def _on_nav_position_changed(self, position: NavPosition) -> None:
        self._grid.removeWidget(self._rail)
        self._rail.set_orientation(position)
        self._place_rail(position)

    def _place_rail(self, position: NavPosition) -> None:
        row, col = _GRID_CELL[position]
        self._grid.addWidget(self._rail, row, col)

    @staticmethod
    def _placeholder_page() -> QWidget:
        from PySide6.QtCore import Qt

        label = QLabel("Dashboard placeholder — pages built in Task 5")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return label
