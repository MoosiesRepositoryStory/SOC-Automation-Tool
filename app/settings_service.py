"""Wraps SettingsRepository with typed access and a Qt signal.

The repo (data/) stays a generic string key/value store on purpose — this
service is where NavPosition <-> str conversion and Qt signalling live,
keeping data/ ignorant of both Qt and this specific domain concept.
"""

import json

from PySide6.QtCore import QObject, Signal

from app.nav.nav_rail import NavPosition
from data.db import connect
from data.repositories.settings_repo import SettingsRepository

_NAV_POSITION_KEY = "nav_position"
_DEFAULT_NAV_POSITION = NavPosition.LEFT

_COLUMN_WIDTHS_KEY_PREFIX = "column_widths:"


class SettingsService(QObject):
    nav_position_changed = Signal(object)  # emits NavPosition

    def __init__(self, connection=None, parent=None):
        super().__init__(parent)
        self._repo = SettingsRepository(connection or connect())

    def nav_position(self) -> NavPosition:
        setting = self._repo.get(_NAV_POSITION_KEY, default=_DEFAULT_NAV_POSITION.value)
        try:
            return NavPosition(setting.value)
        except ValueError:
            return _DEFAULT_NAV_POSITION

    def set_nav_position(self, position: NavPosition) -> None:
        if position == self.nav_position():
            return
        self._repo.set(_NAV_POSITION_KEY, position.value)
        self.nav_position_changed.emit(position)

    # Same repo-backed pattern as nav position: generic string storage in
    # data/, typed (here: dict[int, int]) conversion at this layer. Keyed
    # per table_key so other tables can persist widths without colliding.
    # No change signal — unlike nav position, no other widget needs to
    # react live to one table's column widths.

    def column_widths(self, table_key: str) -> dict[int, int]:
        setting = self._repo.get(_COLUMN_WIDTHS_KEY_PREFIX + table_key)
        if setting is None:
            return {}
        try:
            raw = json.loads(setting.value)
        except json.JSONDecodeError:
            return {}
        return {int(col): int(width) for col, width in raw.items()}

    def set_column_widths(self, table_key: str, widths: dict[int, int]) -> None:
        encoded = json.dumps({str(col): width for col, width in widths.items()})
        self._repo.set(_COLUMN_WIDTHS_KEY_PREFIX + table_key, encoded)
