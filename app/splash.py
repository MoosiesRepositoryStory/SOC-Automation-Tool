"""Splash/loading screen — one of the logo's required application points (Task 3)."""

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QSplashScreen

from app.animation import fade_in_window
from app.resources import LOGO_SVG

APP_NAME = "SOC Automation Tool"
SPLASH_SIZE = 220


def _render_logo_pixmap(size: int) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    renderer = QSvgRenderer(str(LOGO_SVG))
    painter = QPainter(pixmap)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    return pixmap


def show_splash(hold_ms: int = 1200) -> QSplashScreen:
    splash = QSplashScreen(_render_logo_pixmap(SPLASH_SIZE))
    splash.showMessage(
        f"{APP_NAME} — loading…",
        Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
    )
    fade_in_window(splash)
    QTimer.singleShot(hold_ms, splash.close)
    return splash


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    splash = show_splash(hold_ms=2000)
    sys.exit(app.exec())
