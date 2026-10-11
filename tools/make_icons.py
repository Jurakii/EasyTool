"""Render the PNG shelf icons for EasyTool and the example tools (1x, 1.5x and 2x).

Run with Maya's Python, which ships PySide:
    "C:\\Program Files\\Autodesk\\Maya2024\\bin\\mayapy.exe" tools/make_icons.py
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from easytool.qt import QtCore, QtGui, QtSvg  # noqa: E402

SHELVES = "M4 11h16M4 20h16M7 11V5M11 11V6M14 11l2.5-6M7 20v-5M10.5 20v-5"
CROSSHAIR = "M9 12a3 3 0 1 0 6 0a3 3 0 1 0-6 0M12 2v5M12 17v5M2 12h5M17 12h5"
BOTTOM = "M12 4v10M8 10l4 4 4-4M5 19h14"
ORIGIN = "M5 19V5M5 19h14M5 19l9-9M3.5 19a1.5 1.5 0 1 0 3 0a1.5 1.5 0 1 0-3 0"
SPARKLE = "M11 2l2 5 5 2-5 2-2 5-2-5-5-2 5-2zM19 15l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z"

ICONS = [
    ("easytool/resources/icons/easytool", SHELVES, "#F2A43A", "#1A1712"),
    ("examples/pivot-snap/icons/pivotSnap", CROSSHAIR, "#2F6FB0", "#FFFFFF"),
    ("examples/pivot-snap/icons/pivotSnapBottom", BOTTOM, "#2F6FB0", "#FFFFFF"),
    ("examples/pivot-snap/icons/pivotSnapOrigin", ORIGIN, "#2F6FB0", "#FFFFFF"),
    ("examples/scene-cleaner/icons/sceneCleaner", SPARKLE, "#5A6270", "#FFFFFF"),
]


def tile_svg(path_d: str, tile: str, glyph: str) -> bytes:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
        f'<rect x="1" y="1" width="30" height="30" rx="6" fill="{tile}"/>'
        '<g transform="translate(5 5) scale(0.9167)" fill="none" '
        f'stroke="{glyph}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        f'<path d="{path_d}"/></g></svg>'
    ).encode("utf-8")


def render(svg: bytes, size: int, out: str) -> None:
    renderer = QtSvg.QSvgRenderer(QtCore.QByteArray(svg))
    image = QtGui.QImage(size, size, QtGui.QImage.Format_ARGB32_Premultiplied)
    image.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(image)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    renderer.render(painter)
    painter.end()
    os.makedirs(os.path.dirname(out), exist_ok=True)
    if not image.save(out):
        raise RuntimeError(f"Couldn't write {out}")


def main() -> None:
    app = QtGui.QGuiApplication(sys.argv)  # noqa: F841 - Qt needs an app for image plugins
    for rel, path_d, tile, glyph in ICONS:
        base = os.path.join(ROOT, *rel.split("/"))
        svg = tile_svg(path_d, tile, glyph)
        for size, suffix in ((32, ""), (48, "_150"), (64, "_200")):
            render(svg, size, f"{base}{suffix}.png")
        print("wrote", rel)


if __name__ == "__main__":
    main()
