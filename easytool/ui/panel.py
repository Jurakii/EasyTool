"""The EasyTool panel (Layout E, Warm Graphite). Works docked in Maya or as a plain window."""
import os

from easytool.core.installer import KEEP_BOTH, InstallCancelled
from easytool.core.models import Location, ToolInfo, is_newer
from easytool.core.paths import folder_status
from easytool.core.selfupdate import (
    SELF_ID, UpdateError, apply_update, installed_package, is_source_checkout, pick_update, running_version,
)
from easytool.qt import QtCore, QtGui, QtWidgets, exec_, isValid

from . import icons
from .dialogs import SourcesDialog, ask_conflict
from .theme import C, stylesheet
from .widgets import Card, ElidedLabel, EmptyState, Segmented, ToolRow, button, label, open_path, set_prop, tool_button
from .workers import run_async

FOLDERS = (("shelves", "Shelves"), ("icons", "Icons"), ("scripts", "Scripts"))
NEW_SHELF = "__new__"


def plural(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")


def join_names(names) -> str:
    names = list(names)
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


class EasyToolPanel(QtWidgets.QWidget):
    def __init__(self, ctx, parent=None, sync: bool = False):
        super().__init__(parent)
        self.ctx = ctx
        self.sync = sync  # run network work inline (previews and tests)
        self.results = []
        self.visible_ids = set()  # sources whose tools are listed (the update source may be checked silently)
        self.tools = []
        self.selected = set()
        self.filter = "all"
        self.loading = False
        self.busy = False
        self.self_update = None  # a newer EasyTool offered by the update source
        self.self_updated = ""  # version installed over this copy, waiting for a reopen
        self._update_action = "update"
        self._sticky = None

        self.setObjectName("EasyToolPanel")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setStyleSheet(stylesheet())
        self.setMinimumWidth(320)
        self._build()
        self._update_folders()
        self._load_shelves()
        self.refresh_sources()

    # Layout --------------------------------------------------------------

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        body = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(body)
        lay.setContentsMargins(12, 12, 12, 8)
        lay.setSpacing(10)
        root.addWidget(body, 1)

        self.update_bar = QtWidgets.QFrame()
        self.update_bar.setObjectName("UpdateBar")
        bar = QtWidgets.QHBoxLayout(self.update_bar)
        bar.setContentsMargins(12, 10, 10, 10)
        bar.setSpacing(10)
        mark = QtWidgets.QLabel()
        mark.setPixmap(icons.pixmap("download", C["accent"], 16, self.devicePixelRatioF(), 2.2))
        mark.setAlignment(QtCore.Qt.AlignTop)
        bar.addWidget(mark)
        self.update_text = label("", wrap=True)
        bar.addWidget(self.update_text, 1)
        self.update_btn = button("Update", "add")
        self.update_btn.clicked.connect(self._on_update_clicked)
        bar.addWidget(self.update_btn)
        self.update_bar.hide()
        lay.addWidget(self.update_bar)

        row = QtWidgets.QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(label("Shelf", "muted"))
        self.shelf_combo = QtWidgets.QComboBox()
        self.shelf_combo.setAccessibleName("Shelf to add buttons to")
        self.shelf_combo.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.shelf_combo.activated.connect(self._on_shelf_picked)
        row.addWidget(self.shelf_combo, 1)
        self.refresh_btn = tool_button("refresh", "Check sources again")
        self.refresh_btn.clicked.connect(self.refresh_sources)
        row.addWidget(self.refresh_btn)
        self.menu_btn = tool_button("more", "More", C["text"])
        self.menu_btn.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.menu_btn.setMenu(self._build_menu())
        row.addWidget(self.menu_btn)
        lay.addLayout(row)

        self.folders_card = Card("Folders")
        grid = self.folders_card.body_layout
        grid.setColumnMinimumWidth(0, 56)
        grid.setColumnStretch(1, 1)
        self.folder_paths = {}
        for r, (kind, text) in enumerate(FOLDERS):
            grid.addWidget(label(text, "muted"), r, 0)
            path = ElidedLabel(role="mono")
            grid.addWidget(path, r, 1)
            browse = tool_button("folder", f"Choose {text.lower()} folder", size=28, variant="ghost")
            browse.clicked.connect(lambda _=False, k=kind: self._browse(k))
            grid.addWidget(browse, r, 2)
            self.folder_paths[kind] = path
        lay.addWidget(self.folders_card)

        self.search = QtWidgets.QLineEdit()
        self.search.setAccessibleName("Search tools")
        self.search.setClearButtonEnabled(True)
        self.search.addAction(icons.icon("search", C["muted"]), QtWidgets.QLineEdit.LeadingPosition)
        self.search.textChanged.connect(lambda _text: self._render())
        lay.addWidget(self.search)

        self.segments = Segmented([("all", "All"), ("installed", "Installed"), ("updates", "Updates")])
        self.segments.changed.connect(self._on_filter)
        lay.addWidget(self.segments)

        self.banner = QtWidgets.QFrame()
        self.banner.setObjectName("Banner")
        banner_row = QtWidgets.QHBoxLayout(self.banner)
        banner_row.setContentsMargins(10, 8, 10, 8)
        banner_row.setSpacing(8)
        warn = QtWidgets.QLabel()
        warn.setPixmap(icons.pixmap("warning", C["accent_text"], 16, self.devicePixelRatioF()))
        warn.setAlignment(QtCore.Qt.AlignTop)
        banner_row.addWidget(warn)
        self.banner_text = label("", "warn", wrap=True)
        banner_row.addWidget(self.banner_text, 1)
        self.banner.hide()
        lay.addWidget(self.banner)

        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        host = QtWidgets.QWidget()
        host.setObjectName("ToolList")
        self.list_layout = QtWidgets.QVBoxLayout(host)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(4)
        self.scroll.setWidget(host)
        lay.addWidget(self.scroll, 1)

        footer = QtWidgets.QFrame()
        footer.setObjectName("Footer")
        foot = QtWidgets.QVBoxLayout(footer)
        foot.setContentsMargins(12, 10, 12, 12)
        foot.setSpacing(8)
        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.hide()
        foot.addWidget(self.progress)
        self.status = label("", "muted", wrap=True)
        self.status.hide()
        foot.addWidget(self.status)

        actions = QtWidgets.QHBoxLayout()
        actions.setSpacing(8)
        summary = QtWidgets.QVBoxLayout()
        summary.setSpacing(0)
        self.sel_title = label("", "name")
        self.sel_detail = label("", "meta")
        summary.addWidget(self.sel_title)
        summary.addWidget(self.sel_detail)
        actions.addLayout(summary, 1)
        self.remove_btn = button("Remove")
        self.remove_btn.clicked.connect(self._remove_selected)
        actions.addWidget(self.remove_btn)
        self.install_btn = button("Install", "primary")
        self.install_btn.setIcon(icons.icon("download", C["on_accent"], 16, 2.2))
        self.install_btn.clicked.connect(self._install_selected)
        actions.addWidget(self.install_btn)
        foot.addLayout(actions)
        root.addWidget(footer)

    def _build_menu(self) -> QtWidgets.QMenu:
        menu = QtWidgets.QMenu(self)
        menu.addAction("Manage sources…", self._manage_sources)
        menu.addSeparator()
        for kind, text in FOLDERS:
            menu.addAction(f"Open {text.lower()} folder", lambda k=kind: self._open(self.ctx.folders.get(k)))
        menu.addAction("Open modules folder", lambda: self._open(self.ctx.folders.modules))
        menu.addAction("Open EasyTool's data folder", lambda: self._open(self.ctx.settings.root))
        menu.addSeparator()
        menu.addAction("Use Maya's default folders", self._reset_folders)
        return menu

    # Folders and shelf -----------------------------------------------------

    def _update_folders(self) -> None:
        problems, missing = [], 0
        for kind, text in FOLDERS:
            path = self.ctx.folders.get(kind)
            self.folder_paths[kind].setText(path)
            status = folder_status(path)
            if status == "read-only":
                problems.append(f"{text} folder is read-only")
            elif status == "missing":
                missing += 1
        if problems:
            self.folders_card.set_status(problems[0], "error")
        elif missing:
            self.folders_card.set_status(f"{missing} will be created", "muted")
        else:
            self.folders_card.set_status("All found", "ok")

    def _browse(self, kind: str) -> None:
        current = self.ctx.folders.get(kind)
        path = QtWidgets.QFileDialog.getExistingDirectory(self, f"Choose the {kind} folder", current)
        if not path:
            return
        self.ctx.set_folder(kind, os.path.normpath(path))
        self._after_folder_change(kind)

    def _reset_folders(self) -> None:
        for kind, _text in FOLDERS:
            self.ctx.set_folder(kind, "")
        self._after_folder_change("shelves")

    def _after_folder_change(self, kind: str) -> None:
        self._update_folders()
        if kind == "shelves":
            self._load_shelves()

    def _load_shelves(self) -> None:
        try:
            names = list(self.ctx.backend.list_shelves())
        except Exception:
            names = []
        target = self.ctx.settings.shelf
        combo = self.shelf_combo
        combo.blockSignals(True)
        combo.clear()
        if target not in names:
            combo.addItem(f"{target} (new)", target)
        for name in names:
            combo.addItem(name, name)
        combo.insertSeparator(combo.count())
        combo.addItem("New shelf…", NEW_SHELF)
        combo.setCurrentIndex(max(0, combo.findData(target)))
        combo.blockSignals(False)
        self._update_footer()

    def _on_shelf_picked(self, index: int) -> None:
        name = self.shelf_combo.itemData(index)
        if name == NEW_SHELF:
            name, ok = QtWidgets.QInputDialog.getText(self, "New shelf", "Shelf name:")
            if not ok or not name.strip():
                self._load_shelves()
                return
            name = name.strip()
        try:
            self.ctx.settings.shelf = name
        except ValueError as exc:
            self._set_status(str(exc), "error")
        self._load_shelves()

    def _open(self, path: str) -> None:
        if not open_path(path):
            self._set_status(f"That folder doesn't exist yet: {path}", "warn")

    # Sources -------------------------------------------------------------

    def refresh_sources(self) -> None:
        sources = [s for s in self.ctx.settings.sources if s.enabled]
        self.visible_ids = {s.id for s in sources}
        update_source = self.ctx.settings.update_source
        if update_source and update_source.id not in self.visible_ids:
            sources.append(update_source)  # checked for EasyTool updates only; its tools aren't listed
        if not sources:
            self.results = []
            self._merge()
            self._render()
            return
        self.loading = True
        self.refresh_btn.setEnabled(False)
        self._render()
        task = lambda: self.ctx.resolver.list_all(sources)  # noqa: E731
        if self.sync:
            self._on_listed(task())
        else:
            run_async(task, self._on_listed, self._on_list_failed)

    def _on_listed(self, results) -> None:
        if not isValid(self):  # the panel was closed while sources were loading
            return
        self.loading = False
        self.refresh_btn.setEnabled(True)
        self.results = results
        errors = [f"{r.source.name}: {e}" for r in results if r.source.id in self.visible_ids for e in r.errors]
        if errors:
            first = errors[0]
            more = f" (and {plural(len(errors) - 1, 'other problem')})" if len(errors) > 1 else ""
            self.banner_text.setText(first + more)
            self.banner.setToolTip("\n".join(errors))
            self.banner.show()
        else:
            self.banner.hide()
        self._merge()
        self._render()

    def _on_list_failed(self, message: str) -> None:
        if not isValid(self):
            return
        self.loading = False
        self.refresh_btn.setEnabled(True)
        self.banner_text.setText(message)
        self.banner.show()
        self._render()

    def _manage_sources(self) -> None:
        dialog = SourcesDialog(self.ctx.settings, self)
        exec_(dialog)
        if dialog.changed:
            self.refresh_sources()

    def _merge(self) -> None:
        by_id, offers = {}, []
        for result in self.results:
            for tool in result.tools:
                if tool.id == SELF_ID:  # EasyTool itself: an update offer, never a tool to install
                    offers.append(tool)
                    continue
                if result.source.id not in self.visible_ids:
                    continue
                known = by_id.get(tool.id)
                if known is None or is_newer(tool.version, known.version):
                    by_id[tool.id] = tool
        for rec in self.ctx.registry.all():
            preview = next((p for p in rec.files if p.lower().endswith(".png") and os.path.isfile(p)), "")
            if rec.id in by_id:
                if not by_id[rec.id].preview_icon:  # e.g. a feed entry without an "icon"
                    by_id[rec.id].preview_icon = preview
            else:
                by_id[rec.id] = ToolInfo(
                    id=rec.id, name=rec.name, version=rec.version, category=rec.category,
                    description="Installed, but not in any of your sources right now.",
                    location=Location(kind=""), preview_icon=preview,
                )
        self.tools = sorted(by_id.values(), key=lambda t: t.name.lower())
        self.selected &= set(by_id)
        update_source = self.ctx.settings.update_source
        self.self_update = pick_update(offers, update_source.id if update_source else "", running_version())

    # List ----------------------------------------------------------------

    def state(self, tool) -> str:
        rec = self.ctx.registry.get(tool.id)
        if rec is None:
            return "new"
        if tool.location.kind and is_newer(tool.version, rec.version):
            return "update"
        return "installed"

    def _visible(self) -> list:
        query = self.search.text().strip().lower()
        out = []
        for tool in self.tools:
            state = self.state(tool)
            if self.filter == "installed" and state == "new":
                continue
            if self.filter == "updates" and state != "update":
                continue
            haystack = f"{tool.name} {tool.id} {tool.category} {tool.description}".lower()
            if query and query not in haystack:
                continue
            out.append(tool)
        return out

    def _on_filter(self, key: str) -> None:
        self.filter = key
        self._render()

    def _clear_list(self) -> None:
        while self.list_layout.count():
            widget = self.list_layout.takeAt(0).widget()
            if widget:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

    def _render(self) -> None:
        self._clear_list()
        updates = sum(1 for t in self.tools if self.state(t) == "update")
        self.segments.set_text("updates", f"Updates · {updates}" if updates else "Updates")
        self.search.setPlaceholderText(f"Search {plural(len(self.tools), 'tool')}" if self.tools else "Search tools")

        visible = self._visible()
        empty = None
        if self.loading and not self.tools:
            empty = EmptyState("Checking your sources…")
        elif not self.tools:
            empty = EmptyState(
                "No sources yet",
                "Add a GitHub repo, a .zip link, an index.json or a folder to see tools here.",
                "Add a source", self._manage_sources,
            )
        elif not visible:
            query = self.search.text().strip()
            if query:
                empty = EmptyState(f"No tools match “{query}”.")
            elif self.filter == "updates":
                empty = EmptyState("Everything is up to date.")
            else:
                empty = EmptyState("Nothing installed yet.", "Tick tools in All and press Install.")

        if empty:
            self.list_layout.addWidget(empty)
        for tool in visible:
            rec = self.ctx.registry.get(tool.id)
            row = ToolRow(tool, self.state(tool), rec.version if rec else "", tool.id in self.selected)
            row.toggled.connect(self._on_row_toggled)
            row.action.connect(self._on_row_action)
            self.list_layout.addWidget(row)
        self.list_layout.addStretch(1)
        self._update_footer()
        self._update_self_banner()

    def _on_row_toggled(self, tool_id: str, checked: bool) -> None:
        if checked:
            self.selected.add(tool_id)
        else:
            self.selected.discard(tool_id)
        self._update_footer()

    def _tool(self, tool_id: str):
        return next((t for t in self.tools if t.id == tool_id), None)

    def _on_row_action(self, tool_id: str, action: str) -> None:
        tool = self._tool(tool_id)
        if tool is None:
            return
        if action == "install":
            self.install_tools([tool])
        elif action == "uninstall":
            self.remove_tools([tool])
        elif action == "homepage" and tool.homepage:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl(tool.homepage))
        elif action == "files":
            self._open(tool.location.path)

    # Footer --------------------------------------------------------------

    def _selection(self):
        chosen = [t for t in self.tools if t.id in self.selected]
        installable = [t for t in chosen if t.location.kind and self.state(t) != "installed"]
        removable = [t for t in chosen if self.ctx.registry.get(t.id)]
        return chosen, installable, removable

    def _update_footer(self) -> None:
        chosen, installable, removable = self._selection()
        shelf = self.ctx.settings.shelf
        if not chosen:
            self.sel_title.setText("Nothing selected")
            self.sel_detail.setText(f"Buttons go on the {shelf} shelf")
        else:
            self.sel_title.setText(f"{len(chosen)} selected")
            buttons = sum(len(t.buttons) for t in installable)
            if installable and buttons:
                self.sel_detail.setText(f"{plural(buttons, 'button')} for the {shelf} shelf")
            elif installable:
                self.sel_detail.setText(f"{plural(len(installable), 'tool')} to install")
            else:
                self.sel_detail.setText("Already installed")
        verb = "Update" if installable and all(self.state(t) == "update" for t in installable) else "Install"
        self.install_btn.setText(f"{verb} {len(installable)}" if installable else "Install")
        self.install_btn.setEnabled(bool(installable) and not self.busy)
        self.remove_btn.setText(f"Remove {len(removable)}")
        self.remove_btn.setVisible(bool(removable))
        self.remove_btn.setEnabled(not self.busy)

    def _set_status(self, text: str, role: str = "muted") -> None:
        self.status.setText(text)
        set_prop(self.status, "role", role)
        self.status.setVisible(bool(text))

    def _set_busy(self, busy: bool, message: str = "") -> None:
        self.busy = busy
        self.progress.setVisible(busy)
        self.refresh_btn.setEnabled(not busy and not self.loading)
        self.update_btn.setEnabled(not busy)
        if message:
            self._set_status(message)
        self._update_footer()

    # Updating EasyTool itself ----------------------------------------------

    def _update_self_banner(self) -> None:
        if self.self_updated:
            reopen = self.ctx.in_maya
            self.update_text.setText(
                f"EasyTool {self.self_updated} is installed. "
                + ("Reopen EasyTool to start using it." if reopen else "Restart to start using it.")
            )
            self._update_action = "reopen"
            self.update_btn.setText("Reopen")
            self.update_btn.setVisible(reopen)
        elif self.self_update:
            version = self.self_update.version
            package = installed_package()
            if is_source_checkout(package):
                self.update_text.setText(
                    f"EasyTool {version} is available. This copy runs from {os.path.dirname(package)}, so update it there."
                )
                self.update_btn.hide()
            else:
                self.update_text.setText(f"EasyTool {version} is available. You have {running_version()}.")
                self._update_action = "update"
                self.update_btn.setText("Update")
                self.update_btn.show()
        self.update_bar.setVisible(bool(self.self_updated or self.self_update))

    def _on_update_clicked(self) -> None:
        if self._update_action == "reopen":
            from .dock import reopen

            reopen()
            return
        offer = self.self_update
        if self.busy or offer is None:
            return
        self._set_busy(True, f"Downloading EasyTool {offer.version}…")
        task = lambda: self.ctx.resolver.fetch_payload(offer)  # noqa: E731
        if not self.sync:
            run_async(task, self._apply_self_update, self._on_task_failed)
            return
        try:
            payload = task()
        except Exception as exc:  # shown to the user
            self._on_task_failed(str(exc))
            return
        self._apply_self_update(payload)

    def _apply_self_update(self, payload: str) -> None:
        if not isValid(self):
            return
        try:
            version = apply_update(payload, installed_package(), running_version())
        except (UpdateError, OSError) as exc:
            self._set_busy(False)
            self._set_status(str(exc), "error")
            return
        self.self_updated = version
        self._set_busy(False)
        self._set_status(f"Updated EasyTool to {version}.", "ok")
        self._update_self_banner()

    # Install and remove --------------------------------------------------

    def _install_selected(self) -> None:
        self.install_tools(self._selection()[1])

    def _remove_selected(self) -> None:
        self.remove_tools(self._selection()[2])

    def install_tools(self, tools) -> None:
        tools = [t for t in tools if t.location.kind]
        if self.busy or not tools:
            return
        self._set_busy(True, f"Downloading {plural(len(tools), 'tool')}…")
        resolver = self.ctx.resolver

        def fetch():
            out = []
            for tool in tools:
                try:
                    out.append((tool, resolver.fetch_payload(tool), ""))
                except Exception as exc:  # shown to the user per tool
                    out.append((tool, None, str(exc)))
            return out

        if self.sync:
            self._apply_install(fetch())
        else:
            run_async(fetch, self._apply_install, self._on_task_failed)

    def _apply_install(self, fetched) -> None:
        if not isValid(self):  # closed during the download; install nothing
            return
        installer = self.ctx.installer()
        self._sticky = None
        done, failed, stopped = [], [], False
        for tool, payload, error in fetched:
            if error:
                failed.append(f"{tool.name} ({error})")
                continue
            if stopped:
                continue
            self._set_status(f"Installing {tool.name}…")
            try:
                done.append(installer.install(tool, payload, ask=self._ask_conflict))
            except InstallCancelled:
                stopped = True
            except Exception as exc:  # keep going with the other tools
                failed.append(f"{tool.name} ({exc})")
        for rec in done:
            self.selected.discard(rec.id)
        if done:
            try:
                self.ctx.backend.select(self.ctx.settings.shelf)
            except Exception:
                pass

        parts, role = [], "ok"
        if done:
            on_shelf = [r for r in done if r.buttons]
            where = f" on the {self.ctx.settings.shelf} shelf" if on_shelf else ""
            parts.append(f"Installed {join_names(r.name for r in done)}{where}.")
        if stopped:
            parts.append("Install stopped. Files from the tool in progress were put back.")
            role = "warn"
        if failed:
            parts.append(f"Couldn't install {join_names(failed)}.")
            role = "error"
        self._set_busy(False)
        self._set_status(" ".join(parts), role)
        self._load_shelves()
        self._merge()
        self._render()

    def _ask_conflict(self, conflict):
        sticky = self._sticky
        if sticky and (sticky.action != KEEP_BOTH or conflict.can_keep_both):
            return sticky
        decision = ask_conflict(conflict, self)
        if decision.apply_to_all:
            self._sticky = decision
        return decision

    def _on_task_failed(self, message: str) -> None:
        if not isValid(self):
            return
        self._set_busy(False)
        self._set_status(message, "error")

    def remove_tools(self, tools) -> None:
        tools = [t for t in tools if self.ctx.registry.get(t.id)]
        if self.busy or not tools:
            return
        names = join_names(t.name for t in tools)
        box = QtWidgets.QMessageBox(self)
        box.setWindowTitle("Remove tools")
        box.setText(f"Remove {names}?")
        box.setInformativeText(
            "Their shelf buttons, icons, scripts and modules are deleted. "
            "Any of your own files they replaced are put back."
        )
        remove = box.addButton("Remove", QtWidgets.QMessageBox.AcceptRole)
        box.addButton("Cancel", QtWidgets.QMessageBox.RejectRole)
        exec_(box)
        if box.clickedButton() is not remove:
            return
        installer = self.ctx.installer()
        failed = []
        for tool in tools:
            try:
                installer.uninstall(tool.id)
            except Exception as exc:
                failed.append(f"{tool.name} ({exc})")
            self.selected.discard(tool.id)
        if failed:
            self._set_status(f"Couldn't fully remove {join_names(failed)}.", "error")
        else:
            self._set_status(f"Removed {names}.", "ok")
        self._merge()
        self._render()
