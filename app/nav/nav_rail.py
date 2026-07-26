"""Nav rail — a swappable region, not structurally tied to one edge.

Vertical (LEFT/RIGHT) and horizontal (TOP/BOTTOM) are genuinely different
internal layouts, built by two separate methods — not one layout rotated:
vertical items stack icon-above-wrapping-label in a column; horizontal
items sit icon-beside-elided-label in a row. See docs/architecture.md §4.

set_orientation() tears down and rebuilds the inner content widget only —
NavRail itself is never destroyed, so re-parenting it into a different
QGridLayout cell (app/main_window.py) doesn't lose its identity/signals.
No animation here: a nav-position change re-layouts the *parent* of
whatever's animating, which is the second historical Qt bug in CLAUDE.md.
Rebuild, don't fade.
"""

from dataclasses import dataclass
from enum import Enum

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics, QIcon
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

VERTICAL_WIDTH = 96
VERTICAL_ICON_SIZE = 28

HORIZONTAL_HEIGHT = 56
HORIZONTAL_ICON_SIZE = 22
HORIZONTAL_LABEL_MAX_WIDTH = 120

_LARGE_DIMENSION = 16777215  # Qt's own QWIDGETSIZE_MAX, for "no constraint"


class NavPosition(Enum):
    LEFT = "left"
    RIGHT = "right"
    TOP = "top"
    BOTTOM = "bottom"

    @property
    def is_vertical(self) -> bool:
        return self in (NavPosition.LEFT, NavPosition.RIGHT)


@dataclass(frozen=True)
class NavItem:
    item_id: str
    label: str
    icon: QIcon | None = None


class NavRail(QFrame):
    def __init__(
        self,
        items: list[NavItem],
        position: NavPosition = NavPosition.LEFT,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._items = items
        self._position = position

        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(0, 0, 0, 0)
        self._content: QWidget | None = None

        self.set_orientation(position)

    def position(self) -> NavPosition:
        return self._position

    def content_widget(self) -> QWidget:
        """The swappable inner widget — its layout type IS the orientation
        mode (QVBoxLayout for vertical, QHBoxLayout for horizontal), used
        by tests to assert the rebuild actually happened structurally."""
        assert self._content is not None
        return self._content

    def set_orientation(self, position: NavPosition) -> None:
        self._position = position

        if self._content is not None:
            self._outer.removeWidget(self._content)
            # setParent(None) detaches synchronously; deleteLater() alone
            # isn't enough here — Qt only processes DeferredDelete at the
            # outermost event-loop level, so the old content widget was
            # still a child of `self` (and still rendering) through
            # several processEvents() calls in a test with no app.exec().
            self._content.hide()
            self._content.setParent(None)
            self._content.deleteLater()
            self._content = None

        self._content = self._build_vertical() if position.is_vertical else self._build_horizontal()
        self._outer.addWidget(self._content)

        if position.is_vertical:
            self.setFixedWidth(VERTICAL_WIDTH)
            self.setMaximumHeight(_LARGE_DIMENSION)
            self.setMinimumHeight(0)
        else:
            self.setFixedHeight(HORIZONTAL_HEIGHT)
            self.setMaximumWidth(_LARGE_DIMENSION)
            self.setMinimumWidth(0)

    # -- vertical: icon above label, stacked column, label wraps ----------

    def _build_vertical(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(4, 8, 4, 8)
        layout.setSpacing(6)

        for item in self._items:
            layout.addWidget(self._make_vertical_item(item))
        layout.addStretch(1)
        return content

    def _make_vertical_item(self, item: NavItem) -> QWidget:
        widget = QWidget()
        v = QVBoxLayout(widget)
        v.setContentsMargins(2, 2, 2, 2)
        v.setSpacing(2)

        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setFixedHeight(VERTICAL_ICON_SIZE)
        if item.icon is not None:
            icon_label.setPixmap(item.icon.pixmap(VERTICAL_ICON_SIZE, VERTICAL_ICON_SIZE))

        text_label = QLabel(item.label)
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text_label.setWordWrap(True)

        v.addWidget(icon_label)
        v.addWidget(text_label)
        return widget

    # -- horizontal: icon beside label, row, label elides ------------------

    def _build_horizontal(self) -> QWidget:
        content = QWidget()
        layout = QHBoxLayout(content)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(10)

        for item in self._items:
            layout.addWidget(self._make_horizontal_item(item))
        layout.addStretch(1)
        return content

    def _make_horizontal_item(self, item: NavItem) -> QWidget:
        widget = QWidget()
        h = QHBoxLayout(widget)
        h.setContentsMargins(4, 2, 4, 2)
        h.setSpacing(6)

        icon_label = QLabel()
        icon_label.setFixedSize(HORIZONTAL_ICON_SIZE, HORIZONTAL_ICON_SIZE)
        if item.icon is not None:
            icon_label.setPixmap(item.icon.pixmap(HORIZONTAL_ICON_SIZE, HORIZONTAL_ICON_SIZE))

        text_label = QLabel()
        text_label.setFixedWidth(HORIZONTAL_LABEL_MAX_WIDTH)
        metrics = QFontMetrics(text_label.font())
        elided = metrics.elidedText(item.label, Qt.TextElideMode.ElideRight, HORIZONTAL_LABEL_MAX_WIDTH)
        text_label.setText(elided)
        text_label.setToolTip(item.label)

        h.addWidget(icon_label)
        h.addWidget(text_label)
        return widget
