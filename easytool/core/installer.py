"""Copy a tool's icons, scripts and shelf files into Maya's folders and add its shelf buttons.

Anything an install would overwrite is first moved to a staging folder, so a cancelled or
failed install puts everything back. When the install succeeds, the user's own files that were
replaced go to a backup folder (and come back on uninstall); EasyTool's own older files are dropped.
"""
from __future__ import annotations

import datetime
import filecmp
import os
import posixpath
import re
import shutil
import sys
import uuid
from dataclasses import dataclass, replace

from .manifest import IMAGE_EXTS, read_tool
from .registry import InstalledTool
from .shelf import read_shelf_file, shelf_name_from_file, tool_tag

REPLACE, KEEP_BOTH, SKIP, CANCEL = "replace", "keep_both", "skip", "cancel"
IGNORED = ("__pycache__", ".DS_Store", "Thumbs.db", ".git", "*.pyc")
ICON_NAME = re.compile(r"^(?P<base>.+?)(?P<suffix>_150|_200)?(?P<ext>\.[^.]+)$")


@dataclass
class Conflict:
    tool_name: str
    kind: str  # "icon" | "script" | "shelf"
    name: str  # what the user sees, e.g. "pivotSnap.png"
    existing: str  # the file already on disk
    incoming: str  # the file from the tool's download
    can_keep_both: bool = False


@dataclass
class Decision:
    action: str
    apply_to_all: bool = False


class InstallCancelled(Exception):
    pass


class InstallError(Exception):
    pass


def effective_tool(listed, payload: str):
    """Install what was downloaded, under the identity and version it was listed with.

    The listing's version wins so that a feed's version number is what gets recorded; otherwise a
    zip whose own easytool.json wasn't bumped would show as needing an update forever.
    """
    found = read_tool(payload)
    if found is None:
        return listed
    return replace(
        found,
        id=listed.id,
        name=listed.name or found.name,
        version=listed.version or found.version,
        category=found.category if found.has_manifest else listed.category,
        homepage=found.homepage or listed.homepage,
        own_shelf=found.own_shelf or listed.own_shelf,
        location=listed.location,
        source_id=listed.source_id,
    )


def merge_shelf_files(tool, payload: str):
    """Put the buttons from a tool's shelf_*.mel files on the chosen shelf, unless it wants its own tab."""
    if not tool.shelf_files or tool.own_shelf:
        return tool
    buttons = list(tool.buttons)
    for rel in tool.shelf_files:
        path = os.path.join(payload, *rel.split("/"))
        if not os.path.isfile(path):
            raise InstallError(f"{tool.name} lists {rel}, but the download doesn't include it.")
        buttons += read_shelf_file(path)
    return replace(tool, buttons=buttons, shelf_files=[])


def icon_groups(names) -> dict:
    """Group pivotSnap.png with pivotSnap_150.png and pivotSnap_200.png so they move together."""
    groups = {}
    for name in names:
        match = ICON_NAME.match(name)
        key = (match.group("base"), match.group("ext").lower()) if match else (name, "")
        groups.setdefault(key, []).append(name)
    return groups


def renamed_icon(name: str, new_base: str) -> str:
    match = ICON_NAME.match(name)
    return f"{new_base}{match.group('suffix') or ''}{match.group('ext')}"


def _same_file(a: str, b: str) -> bool:
    try:
        return os.path.isfile(a) and os.path.isfile(b) and filecmp.cmp(a, b, shallow=False)
    except OSError:
        return False


def _delete(path: str) -> None:
    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path, ignore_errors=True)
    elif os.path.lexists(path):
        os.remove(path)


def _entries(folder: str) -> list:
    if not folder or not os.path.isdir(folder):
        return []
    return sorted(e for e in os.listdir(folder) if e not in IGNORED and not e.endswith(".pyc"))


def _key(path: str) -> str:
    return os.path.normcase(os.path.normpath(path))


class _Session:
    def __init__(self, staging: str):
        self.staging = staging
        self.created = []
        self.set_aside = []  # (original path, staged path, owned by EasyTool, kind)

    def move_aside(self, path: str, owned: bool, kind: str) -> None:
        os.makedirs(self.staging, exist_ok=True)
        staged = os.path.join(self.staging, uuid.uuid4().hex)
        shutil.move(path, staged)
        self.set_aside.append((path, staged, owned, kind))

    def place(self, src: str, dest: str) -> None:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if os.path.isdir(src):
            shutil.copytree(src, dest, ignore=shutil.ignore_patterns(*IGNORED))
        else:
            shutil.copy2(src, dest)
        self.created.append(dest)

    def rollback(self) -> None:
        for path in reversed(self.created):
            _delete(path)
        for original, staged, _owned, _kind in reversed(self.set_aside):
            if os.path.lexists(staged):
                _delete(original)
                shutil.move(staged, original)
        shutil.rmtree(self.staging, ignore_errors=True)

    def commit(self, backup_dir: str, keep_backups: bool) -> dict:
        backups = {}
        for original, staged, owned, kind in self.set_aside:
            if owned or not keep_backups:
                _delete(staged)
                continue
            folder = os.path.join(backup_dir, kind)
            os.makedirs(folder, exist_ok=True)
            dest = os.path.join(folder, os.path.basename(original))
            if os.path.lexists(dest):
                dest += "." + uuid.uuid4().hex[:6]
            shutil.move(staged, dest)
            backups[original] = dest
        shutil.rmtree(self.staging, ignore_errors=True)
        return backups


class Installer:
    def __init__(self, folders, registry, backend, backup_root: str, shelf: str = "EasyTool", keep_backups: bool = True):
        self.folders = folders
        self.registry = registry
        self.backend = backend
        self.backup_root = backup_root
        self.shelf = shelf
        self.keep_backups = keep_backups

    # Install -------------------------------------------------------------

    def install(self, tool, payload: str, ask=None, progress=None) -> InstalledTool:
        ask = ask or (lambda conflict: Decision(REPLACE))
        say = progress or (lambda message: None)
        tool = merge_shelf_files(effective_tool(tool, payload), payload)
        icons_src = os.path.join(payload, tool.icons_dir) if tool.icons_dir else ""
        scripts_src = os.path.join(payload, tool.scripts_dir) if tool.scripts_dir else ""
        scripts = [(name, os.path.join(scripts_src, name)) for name in _entries(scripts_src)]
        scripts += [(posixpath.basename(rel), os.path.join(payload, *rel.split("/"))) for rel in tool.script_files]
        script_names = [name for name, _src in scripts]
        if not (tool.buttons or tool.shelf_files or _entries(icons_src) or scripts):
            raise InstallError(f"{tool.name} has no buttons, shelves, icons or scripts to install.")

        previous = self.registry.get(tool.id)
        owned = {_key(p) for p in previous.files} if previous else set()
        session = _Session(os.path.join(self.backup_root, ".staging", uuid.uuid4().hex))
        tag = tool_tag(tool.id)
        try:
            say(f"Copying icons for {tool.name}")
            icon_map = self._copy_icons(tool, icons_src, owned, session, ask)
            say(f"Copying scripts for {tool.name}")
            for name, src in scripts:
                self._place(tool, "script", name, src, os.path.join(self.folders.scripts, name), owned, session, ask)
            shelf_files = self._copy_shelf_files(tool, payload, owned, session, ask)

            if previous:
                created = {_key(p) for p in session.created}
                for path in previous.files:
                    if _key(path) not in created and os.path.lexists(path):
                        session.move_aside(path, owned=True, kind="old")

            say(f"Adding {tool.name} to the {self.shelf} shelf")
            buttons = [replace(b, icon=icon_map.get(b.icon, b.icon)) for b in tool.buttons]
            if previous and previous.shelf and (previous.shelf != self.shelf or not buttons):
                self.backend.remove_buttons(previous.shelf, tag)
                self.backend.save(previous.shelf)
            if buttons:
                self.backend.ensure_shelf(self.shelf)
                self.backend.remove_buttons(self.shelf, tag)
                self.backend.add_buttons(self.shelf, buttons, tag)
                self.backend.save(self.shelf)
            new_shelves = [shelf_name_from_file(p) for p in shelf_files]
            for name in (previous.shelf_files if previous else []):
                if name not in new_shelves:
                    self.backend.remove_shelf(name)
            for path in shelf_files:
                self.backend.load_shelf_file(path)
        except BaseException:
            session.rollback()
            raise

        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        backups = session.commit(os.path.join(self.backup_root, f"{stamp}-{tool.id}"), self.keep_backups)
        if previous:
            for original, backup in previous.backups.items():
                backups.setdefault(original, backup)
        rec = InstalledTool(
            id=tool.id,
            name=tool.name,
            version=tool.version,
            category=tool.category,
            source_id=tool.source_id,
            shelf=self.shelf if buttons else "",
            buttons=len(buttons),
            files=list(session.created),
            backups=backups,
            shelf_files=[shelf_name_from_file(p) for p in shelf_files],
            installed_at=datetime.datetime.now().isoformat(timespec="seconds"),
        )
        self.registry.put(rec)
        self._refresh(script_names)
        return rec

    def _copy_icons(self, tool, src_dir: str, owned: set, session: _Session, ask) -> dict:
        names = [n for n in _entries(src_dir)
                 if n.lower().endswith(IMAGE_EXTS) and os.path.isfile(os.path.join(src_dir, n))]
        icon_map = {}
        for (base, _ext), group in icon_groups(names).items():
            main = min(group, key=len)
            clashes = [
                n for n in group
                if os.path.lexists(os.path.join(self.folders.icons, n))
                and _key(os.path.join(self.folders.icons, n)) not in owned
                and not _same_file(os.path.join(src_dir, n), os.path.join(self.folders.icons, n))
            ]
            action = REPLACE
            if clashes:
                shown = main if main in clashes else clashes[0]
                action = ask(Conflict(tool.name, "icon", shown, os.path.join(self.folders.icons, shown),
                                      os.path.join(src_dir, shown), can_keep_both=True)).action
            if action == CANCEL:
                raise InstallCancelled()
            if action == SKIP:
                continue
            new_base = self._free_base(base, group) if action == KEEP_BOTH else base
            for name in group:
                target = renamed_icon(name, new_base) if new_base != base else name
                if target != name:
                    icon_map[name] = target
                src, dest = os.path.join(src_dir, name), os.path.join(self.folders.icons, target)
                if os.path.lexists(dest):
                    is_owned = _key(dest) in owned
                    if not is_owned and _same_file(src, dest):
                        continue
                    session.move_aside(dest, owned=is_owned, kind="icons")
                session.place(src, dest)
        return icon_map

    def _free_base(self, base: str, group) -> str:
        n = 1
        while any(os.path.lexists(os.path.join(self.folders.icons, renamed_icon(name, f"{base}_{n}"))) for name in group):
            n += 1
        return f"{base}_{n}"

    def _place(self, tool, kind: str, name: str, src: str, dest: str, owned: set, session: _Session, ask) -> bool:
        if os.path.lexists(dest):
            if _key(dest) in owned:
                session.move_aside(dest, owned=True, kind=kind)
            elif _same_file(src, dest):
                return False
            else:
                action = ask(Conflict(tool.name, kind, name, dest, src, can_keep_both=False)).action
                if action == CANCEL:
                    raise InstallCancelled()
                if action != REPLACE:
                    return False
                session.move_aside(dest, owned=False, kind=kind)
        session.place(src, dest)
        return True

    def _copy_shelf_files(self, tool, payload: str, owned: set, session: _Session, ask) -> list:
        placed = []
        for rel in tool.shelf_files:
            src = os.path.join(payload, *rel.split("/"))
            if not os.path.isfile(src):
                raise InstallError(f"{tool.name} lists {rel}, but the download doesn't include it.")
            name = os.path.basename(src)
            dest = os.path.join(self.folders.shelves, name)
            if self._place(tool, "shelf", name, src, dest, owned, session, ask):
                placed.append(dest)
        return placed

    def _refresh(self, script_names) -> None:
        """Make Maya pick up new scripts, and forget old copies of updated Python modules."""
        self.backend.refresh_scripts()
        roots = {os.path.splitext(n)[0] for n in script_names}
        scripts_dir = _key(os.path.realpath(self.folders.scripts))
        for name, module in list(sys.modules.items()):
            if name.split(".")[0] not in roots:
                continue
            path = getattr(module, "__file__", None) or ""
            if path and _key(os.path.realpath(path)).startswith(scripts_dir):
                del sys.modules[name]

    # Uninstall -----------------------------------------------------------

    def uninstall(self, tool_id: str):
        rec = self.registry.get(tool_id)
        if rec is None:
            return None
        if rec.shelf:
            self.backend.remove_buttons(rec.shelf, tool_tag(tool_id))
            self.backend.save(rec.shelf)
        for name in rec.shelf_files:
            self.backend.remove_shelf(name)
        for path in rec.files:
            _delete(path)
        shelves_dir = _key(self.folders.shelves)
        for original, backup in rec.backups.items():
            if os.path.lexists(backup) and not os.path.lexists(original):
                os.makedirs(os.path.dirname(original), exist_ok=True)
                shutil.move(backup, original)
                if original.endswith(".mel") and _key(os.path.dirname(original)) == shelves_dir:
                    self.backend.load_shelf_file(original)
        self.registry.remove(tool_id)
        self.backend.refresh_scripts()
        return rec
