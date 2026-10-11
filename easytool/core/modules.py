"""Maya modules: tools that ship a .mod file and keep their scripts, plug-ins and icons in one folder.

A module installs as one folder in Maya's per-version modules folder (maya/<version>/modules), next
to a copy of its .mod file whose paths are rewritten to point at that folder. Tools that ship a
plug-ins/ folder but no .mod file get one written for them.

Maya reads .mod files only when it starts, so session_paths() works out what Maya would have added
to its paths, for the running session to pick up by hand.
"""
from __future__ import annotations

import os
import posixpath
import re
import sys
from dataclasses import dataclass, field

MOD_EXT = ".mod"
HEADER = re.compile(
    r"^(?P<lead>\s*(?P<sign>[+-])\s*(?P<attrs>(?:(?:MAYAVERSION|PLATFORM|LOCALE):\S*\s+)*)"
    r"(?P<name>\S+)\s+(?P<version>\S+)\s+)(?P<path>\S.*?)\s*$",
    re.IGNORECASE,
)
ATTR = re.compile(r"(MAYAVERSION|PLATFORM|LOCALE):(\S*)", re.IGNORECASE)
FOLDER_LINE = re.compile(r"^(?:\[r\]\s*)?(?P<key>scripts|plug-ins|icons|presets)\s*:\s*(?P<path>.+)$", re.IGNORECASE)
ENV_LINE = re.compile(r"^(?P<var>[A-Za-z_][A-Za-z0-9_]*)\s*(?P<op>\+:=|\+=|:=|=)\s*(?P<value>.*)$")
FOLDERS = {  # a module's own subfolders, and the variables Maya adds each one to
    "scripts": ("MAYA_SCRIPT_PATH", "PYTHONPATH"),
    "plug-ins": ("MAYA_PLUG_IN_PATH",),
    "icons": ("XBMLANGPATH",),
    "presets": ("MAYA_PRESET_PATH",),
}


@dataclass
class ModSection:
    """One "+ name version path" entry of a .mod file and the lines under it."""

    name: str
    version: str
    path: str
    enabled: bool = True
    maya: str = ""
    platform: str = ""
    lines: list = field(default_factory=list)

    def applies(self, maya_version: str, platform: str) -> bool:
        return (self.enabled and (not self.maya or self.maya == maya_version)
                and (not self.platform or self.platform.lower() == platform))


def current_platform() -> str:
    """The PLATFORM name .mod files use for this computer."""
    if sys.platform == "win32":
        return "win64"
    return "mac" if sys.platform == "darwin" else "linux"


def read_text(path: str) -> str:
    with open(path, "rb") as fh:
        data = fh.read()
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


def parse_mod(text: str) -> list:
    sections = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "//")):
            continue
        match = HEADER.match(line)
        if match:
            attrs = {key.upper(): value for key, value in ATTR.findall(match.group("attrs"))}
            sections.append(ModSection(
                name=match.group("name"),
                version=match.group("version"),
                path=match.group("path"),
                enabled=match.group("sign") == "+",
                maya=attrs.get("MAYAVERSION", ""),
                platform=attrs.get("PLATFORM", ""),
            ))
        elif sections:
            sections[-1].lines.append(stripped)
    return sections


def find_mod_files(folder: str) -> list:
    """The .mod files at the top of a tool's folder."""
    try:
        names = os.listdir(folder)
    except OSError:
        return []
    return sorted(n for n in names if n.lower().endswith(MOD_EXT) and os.path.isfile(os.path.join(folder, n)))


def mod_version(path: str) -> str:
    try:
        sections = parse_mod(read_text(path))
    except OSError:
        return ""
    return sections[0].version if sections else ""


def folder_name(mod_files, tool_id: str) -> str:
    """The module's folder in Maya's modules folder: named after its .mod file, else the tool."""
    base = os.path.splitext(posixpath.basename(mod_files[0]))[0] if mod_files else tool_id
    return re.sub(r"[^\w.-]+", "_", base).strip("._") or tool_id


def _is_absolute(path: str) -> bool:
    return os.path.isabs(path) or bool(re.match(r"^[A-Za-z]:", path))


def _moved_path(path: str, tool_folder: str, name: str) -> str:
    raw = path.strip().strip('"').replace("\\", "/").rstrip("/")
    rel = "" if _is_absolute(raw) else posixpath.normpath(raw or ".")
    if not rel or rel == ".." or rel.startswith("../"):
        # A path on the author's machine, or outside the download: use the tool's folder of that name, if it has one.
        base = posixpath.basename(raw)
        rel = base if base and os.path.isdir(os.path.join(tool_folder, base)) else "."
    return f"./{name}" if rel == "." else f"./{name}/{rel}"


def rewrite_mod(text: str, tool_folder: str, name: str) -> str:
    """The .mod file for Maya's modules folder: each module's path now points into ./<name>, where
    the tool's folder is copied. Paths inside the tool keep their place, so "./sub" becomes "./<name>/sub"."""
    out = []
    for line in text.splitlines():
        match = HEADER.match(line)
        out.append(match.group("lead") + _moved_path(match.group("path"), tool_folder, name) if match else line)
    return "\n".join(out) + "\n"


def module_text(tool_id: str, version: str, name: str, lines=()) -> str:
    """A .mod file for a tool that ships plug-ins but no .mod file of its own."""
    module = re.sub(r"[^\w.]+", "_", tool_id)
    version = re.sub(r"\s+", "", version or "") or "1.0"
    return "\n".join([f"+ {module} {version} ./{name}", *lines]) + "\n"


def _join(root: str, path: str) -> str:
    path = path.strip().strip('"')
    return os.path.normpath(path if _is_absolute(path) else os.path.join(root, path))


def session_paths(mod_path: str, maya_version: str, platform: str = None) -> list:
    """What Maya adds to its paths for a .mod file when it starts, as (variable, value, append) tuples.

    Only the sections for this Maya version and platform count, and the first one per module name,
    as Maya does. A module's scripts, plug-ins, icons and presets folders are listed when they exist.
    """
    platform = platform or current_platform()
    base = os.path.dirname(os.path.abspath(mod_path))
    out, seen = [], set()
    for section in parse_mod(read_text(mod_path)):
        if section.name in seen or not section.applies(str(maya_version), platform):
            continue
        seen.add(section.name)
        root = _join(base, section.path)
        folders = {key: os.path.join(root, key) for key in FOLDERS}
        env = []
        for line in section.lines:
            match = FOLDER_LINE.match(line)
            if match:
                folders[match.group("key").lower()] = _join(root, match.group("path"))
                continue
            match = ENV_LINE.match(line)
            if match:
                op, value = match.group("op"), match.group("value").strip()
                env.append((match.group("var"), _join(root, value) if ":" in op else value, op.startswith("+")))
        for key, variables in FOLDERS.items():
            if os.path.isdir(folders[key]):
                out += [(var, folders[key], True) for var in variables]
        out += env
    return out
