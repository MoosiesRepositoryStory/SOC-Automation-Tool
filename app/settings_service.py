"""Wraps SettingsRepository with typed access and a Qt signal.

The repo (data/) stays a generic string key/value store on purpose — this
service is where NavPosition <-> str conversion and Qt signalling live,
keeping data/ ignorant of both Qt and this specific domain concept.
"""

from PySide6.QtCore import QObject, Signal

from app.nav.nav_rail import NavPosition
from data.db import connect
from data.repositories.settings_repo import SettingsRepository

_NAV_POSITION_KEY = "nav_position"
_DEFAULT_NAV_POSITION = NavPosition.LEFT


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
