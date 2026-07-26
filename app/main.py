"""Entry point."""

import sys

from PySide6.QtWidgets import QApplication

from app.animation import fade_in_window
from app.main_window import APP_NAME, MainWindow
from app.resources import ICON_THEME_NAME, app_icon
from app.settings_service import SettingsService


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    # Matches packaging/soc-tool.desktop's basename — this is what makes Qt
    # set WM_CLASS to "soc-tool" on X11, so Cinnamon's taskbar/alt-tab
    # picker matches this window to that .desktop entry's icon.
    app.setDesktopFileName(ICON_THEME_NAME)
    app.setWindowIcon(app_icon())

    settings_service = SettingsService()
    window = MainWindow(settings_service=settings_service)
    fade_in_window(window)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
