"""About panel — one of the logo's required application points (Task 3)."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout, QWidget

from app.resources import app_icon

APP_NAME = "SOC Automation Tool"
APP_VERSION = "0.1.0 (pre-release)"


class AboutDialog(QDialog):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(f"About {APP_NAME}")
        self.setWindowIcon(app_icon())
        self.setFixedSize(320, 220)

        icon_label = QLabel()
        icon_label.setPixmap(app_icon().pixmap(72, 72))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        name_label = QLabel(APP_NAME)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setStyleSheet("font-size: 16px; font-weight: bold;")

        version_label = QLabel(f"Version {APP_VERSION}")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(icon_label)
        layout.addWidget(name_label)
        layout.addWidget(version_label)
        layout.addStretch(1)
        layout.addWidget(buttons)
