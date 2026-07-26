"""Resolves app resources (currently: the logo) across dev and installed layouts.

Dev tree: this repo, icon files under packaging/icons/hicolor/.
Installed (.deb): icons live under /usr/share/icons/hicolor/, registered
under the theme name "soc-tool" — QIcon.fromTheme finds them without a
hardcoded path.
"""

from pathlib import Path

from PySide6.QtGui import QIcon

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOGO_SVG = PROJECT_ROOT / "packaging" / "icons" / "hicolor" / "scalable" / "apps" / "soc-tool.svg"

ICON_THEME_NAME = "soc-tool"


def app_icon() -> QIcon:
    icon = QIcon.fromTheme(ICON_THEME_NAME)
    if not icon.isNull():
        return icon
    return QIcon(str(LOGO_SVG))
