"""Find the Maya folders EasyTool writes to."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, replace

FOLDER_KINDS = ("shelves", "icons", "scripts")


def maya_cmds():
    """Return maya.cmds when running inside an interactive Maya session, else None."""
    try:
        from maya import cmds
    except ImportError:
        return None
    if not hasattr(cmds, "shelfLayout"):  # mayapy without maya.standalone
        return None
    try:
        return None if cmds.about(batch=True) else cmds
    except Exception:
        return None


def default_app_dir() -> str:
    """The folder that holds Maya's per-version prefs (Documents/maya on Windows)."""
    env = os.environ.get("MAYA_APP_DIR")
    if env:
        return env
    try:
        from maya import cmds
        return os.path.normpath(cmds.internalVar(userAppDir=True))
    except Exception:
        return os.path.join(os.path.expanduser("~"), "Documents", "maya")


@dataclass
class MayaFolders:
    shelves: str
    icons: str
    scripts: str
    version: str = ""
    modules: str = ""  # maya/<version>/modules, next to the scripts folder unless given

    def __post_init__(self):
        if not self.modules and self.scripts:
            self.modules = os.path.join(os.path.dirname(os.path.normpath(self.scripts)), "modules")

    def get(self, kind: str) -> str:
        return getattr(self, kind)


def detect_maya_folders(app_dir: str = None) -> MayaFolders:
    cmds = maya_cmds()
    if cmds is not None:
        return MayaFolders(
            shelves=os.path.normpath(cmds.internalVar(userShelfDir=True)),
            icons=os.path.normpath(cmds.internalVar(userBitmapsDir=True)),
            scripts=os.path.normpath(cmds.internalVar(userScriptDir=True)),
            version=str(cmds.about(version=True)),
        )
    app_dir = app_dir or default_app_dir()
    versions = []
    if os.path.isdir(app_dir):
        versions = sorted((d for d in os.listdir(app_dir) if re.fullmatch(r"\d{4}", d)), reverse=True)
    version = versions[0] if versions else "2025"
    base = os.path.join(app_dir, version)
    return MayaFolders(
        shelves=os.path.join(base, "prefs", "shelves"),
        icons=os.path.join(base, "prefs", "icons"),
        scripts=os.path.join(base, "scripts"),
        version=version,
    )


def apply_overrides(folders: MayaFolders, overrides: dict) -> MayaFolders:
    picked = {k: v for k, v in (overrides or {}).items() if k in FOLDER_KINDS and v}
    return replace(folders, **picked)


def folder_status(path: str) -> str:
    if not os.path.isdir(path):
        return "missing"
    if not os.access(path, os.W_OK):
        return "read-only"
    return "ok"
