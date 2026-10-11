"""Warm Graphite: the palette, fonts and Qt stylesheet for the panel and its dialogs."""
import os
from string import Template

from easytool.qt import QtCore, QtGui

RESOURCES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources")

C = {
    "bg": "#191816",
    "panel": "#211F1C",
    "raised": "#2B2824",
    "line": "#38342F",
    "line_soft": "#2B2824",
    "box": "#6E6961",
    "text": "#EEE8DE",
    "muted": "#ADA597",
    "faint": "#8E877B",
    "accent": "#F2A43A",
    "accent_hover": "#F5B45A",
    "accent_text": "#F7BE6E",
    "accent_soft": "#3A2C17",
    "accent_line": "#6B4E22",
    "on_accent": "#1A1712",
    "ok": "#9FD59A",
    "danger": "#F4A39A",
    "footer": "#131210",
}

CATEGORY_COLORS = {
    "Modeling": "#2F6FB0",
    "Rigging": "#7A4FB5",
    "Animation": "#C2571A",
    "Lighting": "#A87512",
    "Rendering": "#A8456A",
    "FX": "#2B7A99",
    "Pipeline": "#1F7A6E",
    "Utility": "#5A6270",
}


def category_color(category: str) -> str:
    return CATEGORY_COLORS.get(category, CATEGORY_COLORS["Utility"])


_fonts = None


def fonts():
    """Register the fonts in resources/fonts once. Returns (ui family, its semibold family or "", mono family).

    A static SemiBold file registers as its own family ("Archivo SemiBold"). Naming that family is
    the only way to get SemiBold in both Qt 5 and Qt 6: Qt 5 reads stylesheet weights on its own
    scale, where 600 is Bold and 700 is Black.
    """
    global _fonts
    if _fonts:
        return _fonts
    folder = os.path.join(RESOURCES, "fonts")
    if os.path.isdir(folder):
        for name in sorted(os.listdir(folder)):
            if name.lower().endswith((".ttf", ".otf")):
                # From memory, so the file isn't held open and a self-update can replace it.
                with open(os.path.join(folder, name), "rb") as fh:
                    QtGui.QFontDatabase.addApplicationFontFromData(QtCore.QByteArray(fh.read()))
    try:
        families = set(QtGui.QFontDatabase.families())
    except TypeError:  # PySide2: instance method
        families = set(QtGui.QFontDatabase().families())
    ui = next((f for f in ("Archivo", "Segoe UI", "Helvetica Neue") if f in families), QtGui.QFont().family())
    semibold = next((f for f in (f"{ui} SemiBold", f"{ui} Semibold") if f in families), "")
    mono = next((f for f in ("IBM Plex Mono", "Cascadia Mono", "Consolas", "Menlo") if f in families), ui)
    _fonts = (ui, semibold, mono)
    return _fonts


QSS = Template("""
#EasyToolPanel, #EasyToolDialog { background: $bg; }
QWidget { color: $text; font-family: "$ui"; font-size: 13px; }
QLabel { background: transparent; }
QLabel[role="muted"] { color: $muted; font-size: 12px; }
QLabel[role="title"] { font-size: 16px; $bold; }
QLabel[role="name"] { $semibold; }
QLabel[role="meta"] { color: $muted; font-size: 12px; }
QLabel[role="mono"] { font-family: "$mono"; font-size: 11px; }
QLabel[role="ok"] { color: $ok; font-size: 12px; }
QLabel[role="warn"] { color: $accent_text; font-size: 12px; }
QLabel[role="error"] { color: $danger; font-size: 12px; }

QLineEdit, QComboBox {
    background: $panel; border: 1px solid $line; border-radius: 8px;
    padding: 0 10px; min-height: 32px;
    selection-background-color: $accent; selection-color: $on_accent;
}
QLineEdit:focus, QComboBox:focus, QComboBox:on { border-color: $accent; }
QLineEdit[role="mono"] { font-family: "$mono"; font-size: 12px; }
QComboBox::drop-down { border: 0; width: 26px; subcontrol-origin: padding; subcontrol-position: center right; }
QComboBox::down-arrow { image: url($icons/chevron-down.svg); width: 12px; height: 12px; }
QComboBox QAbstractItemView {
    background: $panel; border: 1px solid $line; outline: 0; padding: 4px;
    selection-background-color: $raised; selection-color: $text;
}

QPushButton {
    background: transparent; border: 1px solid $line; border-radius: 8px;
    padding: 0 12px; min-height: 34px; $semibold;
}
QPushButton:hover { background: $raised; }
QPushButton:pressed { background: $line; }
QPushButton:disabled { color: $faint; border-color: $line_soft; }
QPushButton[variant="primary"] { background: $accent; color: $on_accent; border: 0; $bold; padding: 0 16px; }
QPushButton[variant="primary"]:hover { background: $accent_hover; }
QPushButton[variant="primary"]:disabled { background: $accent_soft; color: $faint; }
QPushButton[variant="add"] {
    border: 1px solid $accent; color: $accent_text; border-radius: 7px;
    min-height: 28px; padding: 0 10px; font-size: 12px;
}
QPushButton[variant="add"]:hover { background: $accent_soft; }
QPushButton[variant="update"] {
    background: $accent_soft; border: 0; color: $accent_text; border-radius: 7px;
    min-height: 28px; padding: 0 10px; font-size: 12px;
}
QPushButton[variant="segment"] { border: 0; border-radius: 7px; color: $muted; min-height: 30px; padding: 0 8px; }
QPushButton[variant="segment"]:hover { color: $text; background: transparent; }
QPushButton[variant="segment"]:checked { background: $accent; color: $on_accent; $bold; }
QPushButton[variant="header"] {
    border: 0; background: transparent; text-align: left;
    padding: 0 10px; min-height: 34px; $semibold;
}

QToolButton { background: $panel; border: 1px solid $line; border-radius: 8px; }
QToolButton:hover { background: $raised; }
QToolButton:disabled { background: transparent; }
QToolButton::menu-indicator { image: none; width: 0; }
QToolButton[variant="ghost"] { background: $raised; border: 0; border-radius: 6px; }
QToolButton[variant="ghost"]:hover { background: $line; }

QFrame#Card { background: $panel; border: 1px solid $line_soft; border-radius: 10px; }
QFrame#Segmented { background: $panel; border: 1px solid $line_soft; border-radius: 9px; }
QFrame#ToolRow { background: transparent; border: 1px solid transparent; border-radius: 8px; }
QFrame#ToolRow:hover { background: $panel; }
QFrame#ToolRow[selected="true"] { background: $raised; border-color: $accent_line; }
QFrame#Footer { background: $footer; border-top: 1px solid $line_soft; }
QFrame#Banner { background: $accent_soft; border-radius: 8px; }
QFrame#UpdateBar { background: $raised; border: 1px solid $accent_line; border-radius: 10px; }
QFrame#Preview { background: $panel; border-radius: 8px; }
QFrame#Option { border: 1px solid $line; border-radius: 8px; }
QFrame#Option[selected="true"] { border-color: $accent; background: $raised; }

QCheckBox, QRadioButton { spacing: 8px; background: transparent; }
QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid $box; border-radius: 4px; background: $bg; }
QCheckBox::indicator:hover { border-color: $accent; }
QCheckBox::indicator:checked { background: $accent; border-color: $accent; image: url($icons/check.svg); }
QRadioButton::indicator { width: 14px; height: 14px; border: 1px solid $box; border-radius: 8px; background: $bg; }
QRadioButton::indicator:checked { width: 8px; height: 8px; border: 4px solid $accent; background: $on_accent; }

QScrollArea { background: transparent; border: 0; }
QWidget#ToolList, QWidget#SourceList { background: transparent; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 0; }
QScrollBar::handle:vertical { background: $line; border-radius: 4px; min-height: 28px; }
QScrollBar::handle:vertical:hover { background: $box; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }

QProgressBar { background: $panel; border: 0; border-radius: 2px; min-height: 4px; max-height: 4px; }
QProgressBar::chunk { background: $accent; border-radius: 2px; }

QMenu { background: $panel; border: 1px solid $line; padding: 4px; }
QMenu::item { padding: 6px 16px; border-radius: 5px; }
QMenu::item:selected { background: $raised; }
QMenu::item:disabled { color: $faint; }
QMenu::separator { height: 1px; background: $line_soft; margin: 4px 6px; }
""")


def stylesheet() -> str:
    ui, semibold_family, mono = fonts()
    semibold = f'font-family: "{semibold_family}"; font-weight: normal' if semibold_family else "font-weight: 600"
    bold = f'font-family: "{ui}"; font-weight: bold'  # "bold" means the same in Qt 5 and Qt 6
    icons = os.path.join(RESOURCES, "icons").replace("\\", "/")
    return QSS.substitute(ui=ui, mono=mono, icons=icons, semibold=semibold, bold=bold, **C)
