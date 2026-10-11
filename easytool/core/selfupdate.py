"""EasyTool updating itself from a feed.

A feed lists EasyTool like any other tool, with the id "easytool" and a link to a release zip
(drag_into_maya.py plus the easytool/ folder). EasyTool never shows that entry as a tool. It only
takes it from the update source (Jurakii/Tools by default), because installing it replaces
EasyTool's own code.
"""
from __future__ import annotations

import datetime
import glob
import os
import re
import shutil

from .models import is_newer, version_key

SELF_ID = "easytool"
VERSION = re.compile(r"""^__version__\s*=\s*["']([^"']+)["']""", re.MULTILINE)


class UpdateError(Exception):
    pass


def installed_package() -> str:
    """The folder of the easytool package that is running."""
    import easytool

    return os.path.dirname(os.path.abspath(easytool.__file__))


def running_version() -> str:
    import easytool

    return easytool.__version__


def is_source_checkout(package: str) -> bool:
    """True for the development copy (next to drag_into_maya.py or in a git checkout), which must not be overwritten."""
    parent = os.path.dirname(os.path.normpath(package))
    return any(os.path.exists(os.path.join(parent, name)) for name in (".git", "drag_into_maya.py"))


def read_version(package: str) -> str:
    try:
        with open(os.path.join(package, "__init__.py"), encoding="utf-8") as fh:
            match = VERSION.search(fh.read())
    except OSError:
        return ""
    return match.group(1) if match else ""


def find_package(payload: str) -> str:
    for candidate in (os.path.join(payload, "easytool"), os.path.join(payload, "scripts", "easytool")):
        if os.path.isfile(os.path.join(candidate, "__init__.py")):
            return candidate
    raise UpdateError("The download doesn't contain EasyTool.")


def pick_update(tools, update_source_id: str, current: str):
    """The newest EasyTool entry offered by the update source, if it's newer than what's running."""
    offers = [t for t in tools if t.id == SELF_ID and t.source_id == update_source_id and is_newer(t.version, current)]
    return max(offers, key=lambda t: version_key(t.version), default=None)


def replace_package(new_package: str, target: str) -> None:
    """Swap the installed easytool folder for the new one, putting the old one back if that fails."""
    parent = os.path.dirname(os.path.normpath(target))
    for leftover in glob.glob(os.path.join(parent, ".easytool-*")):  # from an earlier update that couldn't clean up
        shutil.rmtree(leftover, ignore_errors=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    staging = os.path.join(parent, f".easytool-new-{stamp}")  # dot names can't be imported by accident
    old = os.path.join(parent, f".easytool-old-{stamp}")
    shutil.copytree(new_package, staging, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    try:
        os.rename(target, old)
    except OSError as exc:
        shutil.rmtree(staging, ignore_errors=True)
        raise UpdateError(f"Couldn't replace EasyTool's files ({exc.strerror or exc}). Close anything using them and try again.") from exc
    try:
        os.rename(staging, target)
    except OSError as exc:
        os.rename(old, target)
        shutil.rmtree(staging, ignore_errors=True)
        raise UpdateError(f"Couldn't put the new EasyTool in place ({exc.strerror or exc}). Nothing was changed.") from exc
    shutil.rmtree(old, ignore_errors=True)


def apply_update(payload: str, target: str, current: str) -> str:
    """Install the EasyTool in a downloaded release over the running copy. Returns the new version."""
    if is_source_checkout(target):
        raise UpdateError(f"This EasyTool runs from {os.path.dirname(target)}. Update that copy from its repo instead.")
    new_package = find_package(payload)
    version = read_version(new_package)
    if not version or not is_newer(version, current):
        raise UpdateError(f"The download is EasyTool {version or '(unknown version)'}, which isn't newer than {current}.")
    replace_package(new_package, target)
    return version
