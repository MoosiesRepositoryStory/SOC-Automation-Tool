"""Top-level window fade.

Uses windowOpacity — never QGraphicsOpacityEffect on a top-level window.
See CLAUDE.md: this is one of two historical Qt animation bugs carried
forward from the prior build.
"""

from PySide6.QtCore import QEasingCurve, QPropertyAnimation
from PySide6.QtWidgets import QWidget


def fade_in_window(window: QWidget, duration_ms: int = 200) -> QPropertyAnimation:
    window.setWindowOpacity(0.0)
    window.show()

    anim = QPropertyAnimation(window, b"windowOpacity")
    anim.setDuration(duration_ms)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    # Held on the window itself so it isn't garbage-collected mid-animation.
    window._fade_animation = anim
    return anim
