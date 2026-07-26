"""Generates the app logo: SVG source of truth, then rasterized PNGs.

Run from project root:
    .venv/bin/python packaging/icons/generate_logo.py

Shield-field green is imported directly from app/theme/tokens.py — not
re-picked here — so the mark and the UI chrome can never drift apart.
Steel/silver is mark-specific (not a UI token; nothing else in the app
uses "steel"), so it's defined locally instead of added to tokens.py.

Output, matching the hicolor icon theme layout in docs/architecture.md:
    packaging/icons/hicolor/scalable/apps/soc-tool.svg
    packaging/icons/hicolor/16x16/apps/soc-tool.png
    packaging/icons/hicolor/32x32/apps/soc-tool.png
    packaging/icons/hicolor/64x64/apps/soc-tool.png
    packaging/icons/hicolor/256x256/apps/soc-tool.png
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from app.theme.tokens import Primary  # noqa: E402  (path insert must run first)

STEEL_MAIN = "#C7CCD1"
STEEL_SHADE = "#8B9096"
OUTLINE = "#2E3134"

SHIELD_GREEN = Primary.BASE  # "#1E4620" — the one and only source of this value

ICON_DIR = PROJECT_ROOT / "packaging" / "icons" / "hicolor"
SVG_PATH = ICON_DIR / "scalable" / "apps" / "soc-tool.svg"
SIZES = (16, 32, 64, 256)


def _sword(transform: str) -> str:
    """One sheathed sword: scabbard (tapered, pointed tip), crossguard,
    grip, pommel. Points down/tip-first in local space before `transform`
    rotates and positions it."""
    return f"""
  <g transform="{transform}" stroke="{OUTLINE}" stroke-width="6" stroke-linejoin="round">
    <polygon points="-17,-80 17,-80 17,140 0,185 -17,140" fill="{STEEL_MAIN}"/>
    <rect x="-46" y="-94" width="92" height="16" rx="4" fill="{STEEL_SHADE}"/>
    <rect x="-11" y="-150" width="22" height="58" rx="5" fill="{STEEL_SHADE}"/>
    <circle cx="0" cy="-166" r="17" fill="{STEEL_SHADE}"/>
  </g>"""


def build_svg() -> str:
    swords = _sword("translate(128,128) rotate(40)") + _sword("translate(128,128) rotate(-40)")
    shield = f"""
  <path d="M128,46
           C90,46 55,58 40,70
           L40,128
           C40,185 78,222 128,238
           C178,222 216,185 216,128
           L216,70
           C201,58 166,46 128,46
           Z"
        fill="{SHIELD_GREEN}" stroke="{STEEL_MAIN}" stroke-width="10" stroke-linejoin="round"/>"""

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">
  <title>SOC Automation Tool</title>
{swords}
{shield}
</svg>
"""


def rasterize(svg_path: Path, sizes: tuple[int, ...]) -> list[Path]:
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    renderer = QSvgRenderer(str(svg_path))
    if not renderer.isValid():
        raise RuntimeError(f"QSvgRenderer could not parse {svg_path}")

    written = []
    for size in sizes:
        image = QImage(size, size, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        renderer.render(painter, QRectF(0, 0, size, size))
        painter.end()

        out_path = ICON_DIR / f"{size}x{size}" / "apps" / "soc-tool.png"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if not image.save(str(out_path), "PNG"):
            raise RuntimeError(f"failed to save {out_path}")
        written.append(out_path)
    return written


def main() -> None:
    SVG_PATH.parent.mkdir(parents=True, exist_ok=True)
    SVG_PATH.write_text(build_svg())
    print(f"wrote {SVG_PATH}")

    for path in rasterize(SVG_PATH, SIZES):
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
