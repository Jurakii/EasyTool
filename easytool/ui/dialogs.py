"""The file-conflict dialog and the sources manager."""
import os

from easytool.core.installer import CANCEL, KEEP_BOTH, REPLACE, SKIP, Decision
from easytool.core.manifest import IMAGE_EXTS
from easytool.core.sources import detect_kind, make_source
from easytool.qt import QtCore, QtGui, QtWidgets, exec_

from . import icons
from .theme import C, stylesheet
from .widgets import ElidedLabel, button, label, set_prop, tool_button

WHERE = {"icon": "icon folder", "script": "scripts folder", "shelf": "shelf folder", "module": "modules folder"}


class _Dialog(QtWidgets.QDialog):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("EasyToolDialog")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setStyleSheet(stylesheet())
        self.setWindowTitle(title)
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        self.layout_ = QtWidgets.QVBoxLayout(self)
        self.layout_.setContentsMargins(20, 20, 20, 20)
        self.layout_.setSpacing(14)


class ConflictDialog(_Dialog):
    def __init__(self, conflict, parent=None):
        super().__init__("File already exists", parent)
        self.setFixedWidth(460)
        lay = self.layout_
        thing = "folder" if os.path.isdir(conflict.existing) else "file"

        lay.addWidget(label(f"{conflict.name} already exists", "title", wrap=True))
        lay.addWidget(label(
            f"Your {WHERE.get(conflict.kind, 'folder')} already has a {thing} with this name. "
            "It may belong to another tool or an older install.", "muted", wrap=True))

        if conflict.kind == "icon" and conflict.name.lower().endswith(IMAGE_EXTS):
            row = QtWidgets.QHBoxLayout()
            row.setSpacing(10)
            row.addWidget(self._preview(conflict.existing, "In your folder"))
            row.addWidget(self._preview(conflict.incoming, f"From {conflict.tool_name}"))
            lay.addLayout(row)

        lay.addWidget(label("What should EasyTool do?", "name"))
        self.options = QtWidgets.QButtonGroup(self)
        self.frames = {}
        choices = [(REPLACE, "Replace it", f"Your {thing} moves to EasyTool's backup folder and comes back if you uninstall.")]
        if conflict.can_keep_both:
            choices.append((KEEP_BOTH, "Keep both", "Save the new icons under a new name and point the new buttons at them."))
        skip_text = "Keep your file. The new buttons will use it." if conflict.kind == "icon" else f"Keep your {thing} and don't install this one."
        choices.append((SKIP, "Skip", skip_text))
        for key, title, text in choices:
            lay.addWidget(self._option(key, title, text))
        self.frames[REPLACE][0].setChecked(True)
        self._sync()

        self.apply_all = QtWidgets.QCheckBox("Do the same for every conflict in this install")
        lay.addWidget(self.apply_all)

        buttons = QtWidgets.QHBoxLayout()
        buttons.addStretch(1)
        stop = button("Stop install")
        stop.clicked.connect(self.reject)
        go = button("Continue", "primary")
        go.setDefault(True)
        go.clicked.connect(self.accept)
        buttons.addWidget(stop)
        buttons.addWidget(go)
        lay.addLayout(buttons)
        self.setFixedHeight(lay.totalHeightForWidth(460))

    def _preview(self, path: str, caption: str) -> QtWidgets.QFrame:
        frame = QtWidgets.QFrame()
        frame.setObjectName("Preview")
        row = QtWidgets.QHBoxLayout(frame)
        row.setContentsMargins(10, 10, 10, 10)
        row.setSpacing(10)
        img = QtWidgets.QLabel()
        img.setFixedSize(40, 40)
        dpr = self.devicePixelRatioF()
        pm = QtGui.QIcon(path).pixmap(int(40 * dpr), int(40 * dpr))
        pm.setDevicePixelRatio(dpr)
        img.setPixmap(pm)
        row.addWidget(img)
        row.addWidget(label(caption, "muted", wrap=True), 1)
        return frame

    def _option(self, key: str, title: str, text: str) -> QtWidgets.QFrame:
        frame = QtWidgets.QFrame()
        frame.setObjectName("Option")
        grid = QtWidgets.QGridLayout(frame)
        grid.setContentsMargins(12, 10, 12, 10)
        grid.setHorizontalSpacing(0)
        grid.setVerticalSpacing(2)
        grid.setColumnMinimumWidth(0, 24)
        grid.setColumnStretch(1, 1)
        radio = QtWidgets.QRadioButton(title)
        radio.toggled.connect(self._sync)
        self.options.addButton(radio)
        grid.addWidget(radio, 0, 0, 1, 2)
        grid.addWidget(label(text, "muted", wrap=True), 1, 1)
        self.frames[key] = (radio, frame)
        return frame

    def _sync(self, *_args) -> None:
        for radio, frame in self.frames.values():
            set_prop(frame, "selected", radio.isChecked())

    def decision(self) -> Decision:
        action = next(key for key, (radio, _f) in self.frames.items() if radio.isChecked())
        return Decision(action, self.apply_all.isChecked())


def ask_conflict(conflict, parent=None) -> Decision:
    dialog = ConflictDialog(conflict, parent)
    if exec_(dialog) == QtWidgets.QDialog.Accepted:
        return dialog.decision()
    return Decision(CANCEL)


KIND_ICONS = {"github": "github", "index": "list", "zip": "zip", "folder": "folder"}
DEFAULT_HINT = "A GitHub repo, a feed (index.json), a .zip link, or a local or network folder."
HINTS = {
    "github": "Looks like a GitHub repo. EasyTool reads its index.json feed, or its latest release.",
    "index": "Looks like a feed (index.json) that lists tools.",
    "zip": "Looks like a .zip download.",
    "folder": "Looks like a folder.",
}


class SourcesDialog(_Dialog):
    """Add, switch off and remove sources."""

    def __init__(self, settings, parent=None):
        super().__init__("Sources", parent)
        self.settings = settings
        self.changed = False
        self.setMinimumSize(460, 440)
        lay = self.layout_

        lay.addWidget(label("Sources", "title"))
        lay.addWidget(label("Where EasyTool looks for tools. Paste any link or choose a folder.", "muted", wrap=True))

        row = QtWidgets.QHBoxLayout()
        row.setSpacing(6)
        self.input = QtWidgets.QLineEdit()
        self.input.setProperty("role", "mono")
        self.input.setPlaceholderText("https://github.com/owner/repo")
        self.input.setAccessibleName("Link or folder")
        self.input.textChanged.connect(self._hint)
        self.input.returnPressed.connect(self._add)
        browse = tool_button("folder", "Choose a folder")
        browse.clicked.connect(self._browse)
        add = button("Add", "primary")
        add.clicked.connect(self._add)
        row.addWidget(self.input, 1)
        row.addWidget(browse)
        row.addWidget(add)
        lay.addLayout(row)
        self.hint = label(DEFAULT_HINT, "muted", wrap=True)
        lay.addWidget(self.hint)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        host = QtWidgets.QWidget()
        host.setObjectName("SourceList")
        self.list_layout = QtWidgets.QVBoxLayout(host)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(6)
        scroll.setWidget(host)
        lay.addWidget(scroll, 1)

        footer = QtWidgets.QHBoxLayout()
        footer.addStretch(1)
        done = button("Done", "primary")
        done.clicked.connect(self.accept)
        footer.addWidget(done)
        lay.addLayout(footer)
        self._rebuild()

    def _hint(self, text: str) -> None:
        if not text.strip():
            self.hint.setText(DEFAULT_HINT)
            set_prop(self.hint, "role", "muted")
            return
        try:
            kind = detect_kind(text)
        except ValueError as exc:
            self.hint.setText(str(exc))
            set_prop(self.hint, "role", "warn")
        else:
            self.hint.setText(HINTS[kind])
            set_prop(self.hint, "role", "ok")

    def _browse(self) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Choose a folder of tools")
        if path:
            self.input.setText(os.path.normpath(path))
            self._add()

    def _add(self) -> None:
        try:
            self.settings.add_source(make_source(self.input.text()))
        except ValueError as exc:
            self.hint.setText(str(exc))
            set_prop(self.hint, "role", "error")
            return
        self.input.clear()
        self.changed = True
        self._rebuild()

    def _rebuild(self) -> None:
        while self.list_layout.count():
            widget = self.list_layout.takeAt(0).widget()
            if widget:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        sources = self.settings.sources
        if not sources:
            empty = label("No sources yet.", "muted")
            empty.setAlignment(QtCore.Qt.AlignCenter)
            self.list_layout.addWidget(empty)
        for source in sources:
            self.list_layout.addWidget(self._row(source))
        self.list_layout.addStretch(1)

    def _row(self, source) -> QtWidgets.QFrame:
        frame = QtWidgets.QFrame()
        frame.setObjectName("Card")
        row = QtWidgets.QHBoxLayout(frame)
        row.setContentsMargins(10, 8, 8, 8)
        row.setSpacing(10)
        badge = QtWidgets.QLabel()
        badge.setPixmap(icons.pixmap(KIND_ICONS.get(source.kind, "list"), C["accent"], 18, self.devicePixelRatioF()))
        row.addWidget(badge)
        text = QtWidgets.QVBoxLayout()
        text.setSpacing(0)
        text.addWidget(label(f"{source.name}  ·  {source.kind_label}", "name"))
        text.addWidget(ElidedLabel(source.url, "mono"))
        row.addLayout(text, 1)
        enabled = QtWidgets.QCheckBox("On")
        enabled.setAccessibleName(f"Use {source.name}")
        enabled.setChecked(source.enabled)
        enabled.toggled.connect(lambda on, sid=source.id: self._toggle(sid, on))
        row.addWidget(enabled)
        remove = tool_button("trash", f"Remove {source.name}", C["muted"], 30, "ghost")
        remove.clicked.connect(lambda _=False, sid=source.id: self._remove(sid))
        row.addWidget(remove)
        return frame

    def _toggle(self, source_id: str, on: bool) -> None:
        self.settings.set_source_enabled(source_id, on)
        self.changed = True

    def _remove(self, source_id: str) -> None:
        self.settings.remove_source(source_id)
        self.changed = True
        self._rebuild()
