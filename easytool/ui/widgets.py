"""Small building blocks for the panel: labels, buttons, cards, the filter control and tool rows."""
import os

from easytool.qt import QtCore, QtGui, QtWidgets, Signal, exec_

from . import icons
from .theme import C

POINTER = QtCore.Qt.PointingHandCursor


def set_prop(widget, name: str, value) -> None:
    """Change a property the stylesheet reacts to, and restyle.

    Restyles by re-applying the widget's own (blank) stylesheet. The usual
    widget.style().unpolish()/polish() hands Python Maya's application style, which PySide2
    then frees, corrupting Maya's memory and crashing it.
    """
    widget.setProperty(name, value)
    flip = not widget.property("easytoolRestyle")
    widget.setProperty("easytoolRestyle", flip)
    widget.setStyleSheet(widget.styleSheet().rstrip() + (" " if flip else "  "))


def label(text: str = "", role: str = None, wrap: bool = False) -> QtWidgets.QLabel:
    lbl = QtWidgets.QLabel(text)
    if role:
        lbl.setProperty("role", role)
    lbl.setWordWrap(wrap)
    return lbl


def button(text: str, variant: str = None) -> QtWidgets.QPushButton:
    btn = QtWidgets.QPushButton(text)
    if variant:
        btn.setProperty("variant", variant)
    btn.setCursor(POINTER)
    return btn


def tool_button(icon_name: str, tooltip: str, color: str = None, size: int = 34, variant: str = None) -> QtWidgets.QToolButton:
    btn = QtWidgets.QToolButton()
    btn.setIcon(icons.icon(icon_name, color or C["accent"]))
    btn.setIconSize(QtCore.QSize(16, 16))
    btn.setFixedSize(size, size)
    btn.setToolTip(tooltip)
    btn.setAccessibleName(tooltip)
    btn.setCursor(POINTER)
    if variant:
        btn.setProperty("variant", variant)
    return btn


class ElidedLabel(QtWidgets.QLabel):
    """Shows as much of a long path as fits, with the full text in the tooltip."""

    def __init__(self, text: str = "", role: str = None, mode=QtCore.Qt.ElideMiddle):
        super().__init__()
        self._full = ""
        self._mode = mode
        if role:
            self.setProperty("role", role)
        self.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        self.setText(text)

    def setText(self, text: str) -> None:  # noqa: N802 - Qt naming
        self._full = text or ""
        self.setToolTip(self._full)
        self._elide()

    def full_text(self) -> str:
        return self._full

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._elide()

    def _elide(self) -> None:
        width = max(10, self.width())
        QtWidgets.QLabel.setText(self, self.fontMetrics().elidedText(self._full, self._mode, width))

    def minimumSizeHint(self):  # noqa: N802
        return QtCore.QSize(10, super().minimumSizeHint().height())


class Card(QtWidgets.QFrame):
    """A rounded panel with a header that collapses its body."""

    def __init__(self, title: str):
        super().__init__()
        self.setObjectName("Card")
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        head = QtWidgets.QHBoxLayout()
        head.setContentsMargins(0, 0, 12, 0)
        self.header = button(title, "header")
        self.header.setIconSize(QtCore.QSize(12, 12))
        self.header.clicked.connect(self.toggle)
        self.status = label("", "ok")
        head.addWidget(self.header, 1)
        head.addWidget(self.status)
        outer.addLayout(head)

        self.body = QtWidgets.QWidget()
        self.body_layout = QtWidgets.QGridLayout(self.body)
        self.body_layout.setContentsMargins(12, 0, 12, 12)
        self.body_layout.setHorizontalSpacing(8)
        self.body_layout.setVerticalSpacing(6)
        outer.addWidget(self.body)
        self._sync()

    def toggle(self) -> None:
        self.body.setVisible(not self.body.isVisible())
        self._sync()

    def set_expanded(self, expanded: bool) -> None:
        self.body.setVisible(expanded)
        self._sync()

    def _sync(self) -> None:
        open_ = not self.body.isHidden()
        self.header.setIcon(icons.icon("chevron_down" if open_ else "chevron_right", C["text"], 12, 2.4))
        self.header.setAccessibleDescription("expanded" if open_ else "collapsed")

    def set_status(self, text: str, role: str = "ok") -> None:
        self.status.setText(text)
        set_prop(self.status, "role", role)


class Segmented(QtWidgets.QFrame):
    """All / Installed / Updates."""

    changed = Signal(str)

    def __init__(self, options):
        super().__init__()
        self.setObjectName("Segmented")
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(0)
        self.group = QtWidgets.QButtonGroup(self)
        self.buttons = {}
        for key, text in options:
            btn = button(text, "segment")
            btn.setCheckable(True)
            btn.clicked.connect(lambda _checked=False, k=key: self.changed.emit(k))
            self.group.addButton(btn)
            layout.addWidget(btn, 1)
            self.buttons[key] = btn
        next(iter(self.buttons.values())).setChecked(True)

    def set_text(self, key: str, text: str) -> None:
        self.buttons[key].setText(text)


class ToolRow(QtWidgets.QFrame):
    """One tool in the list: checkbox, tile, name and version, and its action."""

    toggled = Signal(str, bool)
    action = Signal(str, str)  # tool id, "install" | "uninstall" | "homepage" | "files"

    def __init__(self, tool, state: str, installed_version: str, selected: bool):
        super().__init__()
        self.tool = tool
        self.state = state
        self.setObjectName("ToolRow")
        self.setCursor(POINTER)
        self.setMinimumHeight(48)
        if tool.description:
            self.setToolTip(tool.description)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(10)

        self.check = QtWidgets.QCheckBox()
        self.check.setAccessibleName(f"Select {tool.name}")
        self.check.setChecked(selected)
        self.check.toggled.connect(self._on_toggled)
        layout.addWidget(self.check)

        self.tile = QtWidgets.QLabel()
        self.tile.setFixedSize(32, 32)
        layout.addWidget(self.tile)

        text = QtWidgets.QVBoxLayout()
        text.setSpacing(0)
        self.name = ElidedLabel(tool.name, "name", QtCore.Qt.ElideRight)
        version = tool.version or "?"
        if state == "update":
            meta = f"{installed_version} → {version} · {tool.category}"
        else:
            meta = f"{installed_version or version} · {tool.category}" if (installed_version or tool.version) else tool.category
        self.meta = ElidedLabel(meta, "meta", QtCore.Qt.ElideRight)
        text.addWidget(self.name)
        text.addWidget(self.meta)
        layout.addLayout(text, 1)

        if state == "new":
            act = button("Add", "add")
            act.setAccessibleName(f"Install {tool.name}")
            act.clicked.connect(lambda: self.action.emit(tool.id, "install"))
            layout.addWidget(act)
        elif state == "update":
            act = button("Update", "update")
            act.setAccessibleName(f"Update {tool.name}")
            act.clicked.connect(lambda: self.action.emit(tool.id, "install"))
            layout.addWidget(act)
        else:
            done = QtWidgets.QHBoxLayout()
            done.setSpacing(4)
            mark = QtWidgets.QLabel()
            mark.setPixmap(icons.pixmap("check", C["ok"], 13, self.devicePixelRatioF(), 2.6))
            done.addWidget(mark)
            done.addWidget(label("Installed", "ok"))
            layout.addLayout(done)

        self.setProperty("selected", selected)  # not styled yet, so no restyle needed

    def showEvent(self, event):  # noqa: N802 - pixmap needs the real screen scale
        super().showEvent(event)
        self.tile.setPixmap(icons.tool_tile(self.tool, 32, self.devicePixelRatioF()))

    def _on_toggled(self, checked: bool) -> None:
        set_prop(self, "selected", checked)
        self.toggled.emit(self.tool.id, checked)

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == QtCore.Qt.LeftButton:
            self.check.toggle()
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):  # noqa: N802
        menu = QtWidgets.QMenu(self)
        can_fetch = bool(self.tool.location.kind)
        if self.state == "new" and can_fetch:
            menu.addAction("Install", lambda: self.action.emit(self.tool.id, "install"))
        elif self.state == "update" and can_fetch:
            menu.addAction("Update", lambda: self.action.emit(self.tool.id, "install"))
        elif can_fetch:
            menu.addAction("Reinstall", lambda: self.action.emit(self.tool.id, "install"))
        if self.state != "new":
            menu.addAction("Uninstall", lambda: self.action.emit(self.tool.id, "uninstall"))
        if self.tool.homepage:
            menu.addSeparator()
            menu.addAction("Open homepage", lambda: self.action.emit(self.tool.id, "homepage"))
        if self.tool.location.kind == "folder":
            menu.addAction("Show files", lambda: self.action.emit(self.tool.id, "files"))
        exec_(menu, event.globalPos())


class EmptyState(QtWidgets.QWidget):
    def __init__(self, title: str, text: str = "", action_text: str = "", on_action=None):
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 32, 16, 16)
        layout.setSpacing(6)
        heading = label(title, "name")
        heading.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(heading)
        if text:
            body = label(text, "muted", wrap=True)
            body.setAlignment(QtCore.Qt.AlignCenter)
            layout.addWidget(body)
        if action_text:
            btn = button(action_text, "primary")
            btn.clicked.connect(on_action)
            row = QtWidgets.QHBoxLayout()
            row.addStretch(1)
            row.addWidget(btn)
            row.addStretch(1)
            layout.addSpacing(8)
            layout.addLayout(row)


def open_path(path: str) -> bool:
    if not os.path.exists(path):
        return False
    return QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(path))
