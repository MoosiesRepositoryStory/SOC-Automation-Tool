"""Entry point."""

import sys

from PySide6.QtWidgets import QApplication

from app.animation import fade_in_window
from app.main_window import APP_NAME, MainWindow
from app.resources import ICON_THEME_NAME, app_icon
from app.settings_service import SettingsService


def main() -> int:
    app = QApplication(sys.argv)
    # setApplicationName is what actually sets WM_CLASS's class field on
    # X11 in this Qt/PySide6 version — verified on the real X11 session
    # with xprop, not assumed: WM_CLASS came back ("main.py", APP_NAME).
    # setDesktopFileName (below) does NOT affect X11 WM_CLASS here, despite
    # Qt's docs suggesting it should — that was Task 3's original, wrong
    # assumption. Kept anyway for Wayland's app_id, where it does apply.
    # packaging/soc-tool.desktop's StartupWMClass is matched to APP_NAME
    # for exactly this reason — see that file's comment.
    app.setApplicationName(APP_NAME)
    app.setDesktopFileName(ICON_THEME_NAME)
    app.setWindowIcon(app_icon())

    settings_service = SettingsService()
    window = MainWindow(settings_service=settings_service)
    fade_in_window(window)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
