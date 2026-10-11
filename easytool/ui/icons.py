"""Stroke icons drawn from SVG path data and tinted at runtime, plus tool tiles."""
import os

from easytool.qt import QtCore, QtGui, QtSvg

from .theme import category_color

PATHS = {
    "refresh": "M20 12a8 8 0 1 1-2.3-5.6M20 4v5h-5",
    "folder": "M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
    "search": "M5 11a6 6 0 1 0 12 0a6 6 0 1 0-12 0M20 20l-4.2-4.2",
    "check": "M5 12.5l4.5 4.5L19 7",
    "chevron_down": "M6 9l6 6 6-6",
    "chevron_right": "M9 6l6 6-6 6",
    "download": "M12 4v11M7 10l5 5 5-5M5 20h14",
    "more": "M5 12h.01M12 12h.01M19 12h.01",
    "plus": "M12 5v14M5 12h14",
    "trash": "M5 7h14M10 7V5h4v2M7 7l1 12h8l1-12",
    "warning": "M12 4l9 16H3zM12 10v4M12 17v.01",
    "github": "M6 4a2 2 0 1 0 0 4a2 2 0 1 0 0-4M6 16a2 2 0 1 0 0 4a2 2 0 1 0 0-4M18 6a2 2 0 1 0 0 4a2 2 0 1 0 0-4M6 8v8M18 10c0 4-6 3-10 6.5",
    "list": "M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01",
    "zip": "M6 3h9l4 4v14H6zM12 6v1M12 9v1M12 12v1M11 15h2v3h-2z",
}
STROKES = {"more": 3.2}


def _svg(name: str, color: str, stroke: float) -> bytes:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        f'<path d="{PATHS[name]}" fill="none" stroke="{color}" stroke-width="{stroke}" '
        'stroke-linecap="round" stroke-linejoin="round"/></svg>'
    ).encode("utf-8")


def _render(svg: bytes, px: int) -> QtGui.QPixmap:
    renderer = QtSvg.QSvgRenderer(QtCore.QByteArray(svg))
    pm = QtGui.QPixmap(px, px)
    pm.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(pm)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    renderer.render(painter)
    painter.end()
    return pm


def icon(name: str, color: str, size: int = 16, stroke: float = 1.8) -> QtGui.QIcon:
    stroke = STROKES.get(name, stroke)
    result = QtGui.QIcon()
    for scale in (1, 2):
        result.addPixmap(_render(_svg(name, color, stroke), size * scale))
    return result


def pixmap(name: str, color: str, size: int, dpr: float = 1.0, stroke: float = 1.8) -> QtGui.QPixmap:
    pm = _render(_svg(name, color, STROKES.get(name, stroke)), int(size * dpr))
    pm.setDevicePixelRatio(dpr)
    return pm


def _initials(tool) -> str:
    for button in tool.buttons:
        if button.label:
            return button.label[:3].upper()
    words = [w for w in tool.name.replace("-", " ").split() if w]
    return "".join(w[0] for w in words[:2]).upper() or "?"


def tool_tile(tool, size: int = 32, dpr: float = 1.0) -> QtGui.QPixmap:
    """The tool's own icon if we have it, else a category-colored tile with its label."""
    px = int(size * dpr)
    pm = QtGui.QPixmap(px, px)
    pm.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(pm)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
    image = QtGui.QPixmap()
    if tool.preview_icon and os.path.isfile(tool.preview_icon):
        image = QtGui.QIcon(tool.preview_icon).pixmap(px, px)
    if not image.isNull():
        scaled = image.scaled(px, px, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        painter.drawPixmap((px - scaled.width()) // 2, (px - scaled.height()) // 2, scaled)
    else:
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor(category_color(tool.category)))
        radius = px * 0.2
        painter.drawRoundedRect(QtCore.QRectF(0, 0, px, px), radius, radius)
        font = QtGui.QFont()
        font.setBold(True)
        font.setPixelSize(max(8, int(px * 0.32)))
        painter.setFont(font)
        painter.setPen(QtGui.QColor("#FFFFFF"))
        painter.drawText(QtCore.QRectF(0, 0, px, px), QtCore.Qt.AlignCenter, _initials(tool))
    painter.end()
    pm.setDevicePixelRatio(dpr)
    return pm
