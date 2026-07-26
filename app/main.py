"""Entry point.

Minimal scaffold for Task 3 (logo application points). The real dashboard
and swappable nav rail are built in Task 4 — this window is a placeholder
just sufficient to demonstrate setWindowIcon and the window-fade
constraint.
"""

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow

from app.animation import fade_in_window
from app.resources import ICON_THEME_NAME, app_icon

APP_NAME = "SOC Automation Tool"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.resize(900, 600)

        placeholder = QLabel("Dashboard placeholder — built in Task 4")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(placeholder)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    # Matches packaging/soc-tool.desktop's basename — this is what makes Qt
    # set WM_CLASS to "soc-tool" on X11, so Cinnamon's taskbar/alt-tab
    # picker matches this window to that .desktop entry's icon.
    app.setDesktopFileName(ICON_THEME_NAME)
    app.setWindowIcon(app_icon())

    window = MainWindow()
    fade_in_window(window)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
