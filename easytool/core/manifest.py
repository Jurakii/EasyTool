"""Read easytool.json, or work out a tool from its folder layout when there is none."""
from __future__ import annotations

import glob
import json
import os
import re

from .models import CATEGORIES, LANGUAGES, ButtonSpec, ToolInfo, slugify
from .modules import find_mod_files, mod_version
from .shelf import buttons_from_python_text

MANIFEST_NAME = "easytool.json"
INDEX_NAME = "index.json"
IMAGE_EXTS = (".png", ".svg", ".xpm", ".jpg", ".jpeg", ".bmp", ".gif")
SCRIPT_EXTS = (".mel", ".py")
NOT_TOOL_SCRIPTS = ("usersetup.py", "usersetup.mel", "setup.py", "__init__.py")
NOT_TOOL_PACKAGES = ("easytool",)  # EasyTool's own release zip is never a tool
ICON_DIRS = ("icons", "prefs/icons")  # the second is Maya's own layout, as in maya/<version>/prefs
SHELF_GLOBS = ("shelves/shelf_*.mel", "prefs/shelves/shelf_*.mel", "shelf_*.mel")
TOOL_PARTS = ("scripts", "icons", "shelves", "plug-ins", "prefs", "presets")  # folders that are part of a tool
NOT_CODE_DIRS = ("tests", "test", "docs", "doc", "examples", "example", "site-packages", "__pycache__")
MAX_CODE_FILES = 500
MAX_CODE_BYTES = 1 << 20
SIZE_SUFFIX = re.compile(r"_(150|200)\.[^.]+$")


class ManifestError(ValueError):
    pass


def normalize_category(text: str) -> str:
    category = (text or "Utility").strip().title()
    if category.upper() == "FX":
        return "FX"
    return category if category in CATEGORIES else (category or "Utility")


def _text(data: dict, key: str, default: str = "") -> str:
    value = data.get(key, default)
    return default if value is None else str(value).strip()


def _folder(data: dict, key: str, default: str) -> str:
    return _text(data, key, default).replace("\\", "/").strip("/")


def parse_manifest(data, fallback_name: str = "tool") -> ToolInfo:
    if not isinstance(data, dict):
        raise ManifestError("easytool.json must contain a JSON object")

    name = _text(data, "name") or fallback_name

    raw_buttons = data.get("buttons") or []
    if not isinstance(raw_buttons, list):
        raise ManifestError('"buttons" must be a list')
    buttons = []
    for number, raw in enumerate(raw_buttons, 1):
        if not isinstance(raw, dict):
            raise ManifestError(f"button {number} must be an object")
        language = _text(raw, "language", "python").lower()
        if language not in LANGUAGES:
            raise ManifestError(f'button {number}: "language" must be "python" or "mel"')
        command = _text(raw, "command")
        if not command:
            raise ManifestError(f"button {number} has no command")
        buttons.append(ButtonSpec(
            label=_text(raw, "label"),
            tooltip=_text(raw, "tooltip"),
            icon=_text(raw, "icon"),
            command=command,
            language=language,
            double_click=_text(raw, "doubleClick"),
            overlay=_text(raw, "overlay"),
        ))

    shelf = data.get("shelf") or []
    if isinstance(shelf, str):
        shelf = [shelf]
    if not isinstance(shelf, list):
        raise ManifestError('"shelf" must be a path or a list of paths')

    return ToolInfo(
        id=slugify(_text(data, "id") or name),
        name=name,
        version=_text(data, "version"),
        description=_text(data, "description"),
        category=normalize_category(_text(data, "category", "Utility")),
        author=_text(data, "author"),
        maya=_text(data, "maya"),
        homepage=_text(data, "homepage"),
        icon=_text(data, "icon"),
        icons_dir=_folder(data, "icons", "icons"),
        scripts_dir=_folder(data, "scripts", "scripts"),
        shelf_files=[str(p).replace("\\", "/") for p in shelf],
        own_shelf=bool(data.get("ownShelf", False)),
        buttons=buttons,
    )


def find_preview_icon(folder: str, tool: ToolInfo) -> str:
    for name in [tool.icon] + [b.icon for b in tool.buttons]:
        if name:
            path = os.path.join(folder, tool.icons_dir, name)
            if os.path.isfile(path):
                return path
    return ""


def load_manifest(folder: str):
    """Return the ToolInfo from folder/easytool.json, or None if there is no manifest."""
    path = os.path.join(folder, MANIFEST_NAME)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except ValueError as exc:
        raise ManifestError(f"{path} is not valid JSON: {exc}") from exc
    tool = parse_manifest(data, fallback_name=os.path.basename(os.path.normpath(folder)))
    _find_module(folder, tool)
    tool.preview_icon = find_preview_icon(folder, tool)
    return tool


def _find_module(folder: str, tool: ToolInfo) -> None:
    """A tool with a .mod file, or with plug-ins, installs as a Maya module, keeping its folder whole."""
    tool.mod_files = find_mod_files(folder)
    tool.module = bool(tool.mod_files) or os.path.isdir(os.path.join(folder, "plug-ins"))
    if tool.mod_files and not tool.version:
        tool.version = mod_version(os.path.join(folder, tool.mod_files[0]))


def root_scripts(folder: str) -> list:
    """Loose .mel/.py files next to shelves/ and icons/, as in "drag into your prefs" zips."""
    out = []
    for name in sorted(os.listdir(folder)):
        lower = name.lower()
        if not (lower.endswith(SCRIPT_EXTS) and os.path.isfile(os.path.join(folder, name))):
            continue
        if lower in NOT_TOOL_SCRIPTS or lower.startswith(("install", "drag", "shelf_")):
            continue
        out.append(name)
    return out


def root_packages(folder: str) -> list:
    """Python packages (folders with an __init__.py) at the top, for zips that hold no scripts/ folder."""
    return [
        name for name in sorted(os.listdir(folder))
        if os.path.isfile(os.path.join(folder, name, "__init__.py"))
        and not name.startswith((".", "_", "test")) and name.lower() not in NOT_TOOL_PACKAGES
    ]


def is_wrapper(folder: str) -> bool:
    """True for a folder that only wraps a tool, as archives often do, rather than being part of one."""
    return (os.path.isdir(folder) and os.path.basename(folder).lower() not in TOOL_PARTS
            and not os.path.isfile(os.path.join(folder, "__init__.py")))


def find_images(folder: str) -> dict:
    """The image files anywhere in a tool's folder by name, as {name: path}; one in an icons folder wins."""
    found = {}
    for dirpath, dirnames, filenames in os.walk(folder):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith(".") and d.lower() not in NOT_CODE_DIRS)
        in_icons = os.path.basename(dirpath).lower() == "icons"
        for name in sorted(filenames):
            if name.lower().endswith(IMAGE_EXTS) and (name not in found or in_icons and not found[name][0]):
                found[name] = (in_icons, os.path.join(dirpath, name))
    return {name: path for name, (_in_icons, path) in found.items()}


def _python_files(folder: str):
    """The tool's .py files, top folder first; tests, docs and examples are left out."""
    count = 0
    for dirpath, dirnames, filenames in os.walk(folder):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith(".") and d.lower() not in NOT_CODE_DIRS)
        for name in sorted(filenames):
            if name.lower().endswith(".py") and not name.lower().startswith("test"):
                count += 1
                if count > MAX_CODE_FILES:
                    return
                yield os.path.join(dirpath, name)


def code_buttons(folder: str, images=()) -> list:
    """The shelf buttons a tool's Python code makes, for tools that ship no shelf file (see
    shelf.buttons_from_python_text). A button with no image takes the tool's only icon, if it has one."""
    buttons, seen = [], set()
    for path in _python_files(folder):
        try:
            with open(path, "rb") as fh:
                data = fh.read(MAX_CODE_BYTES + 1)
        except OSError:
            continue
        if len(data) > MAX_CODE_BYTES or b"shelfButton" not in data:
            continue
        for button in buttons_from_python_text(data.decode("utf-8", errors="replace"), images):
            if (button.command, button.double_click) not in seen:
                seen.add((button.command, button.double_click))
                buttons.append(button)
    mains = [name for name in images if not SIZE_SUFFIX.search(name)]
    for button in buttons:
        if not button.icon and len(mains) == 1:
            button.icon = mains[0]
    return buttons


def scan_folder(folder: str):
    """Build a tool from a folder with no manifest, from the layouts tools are shared in:

    - "drag into your prefs" files: shelves/, icons/, and scripts/ or loose scripts
    - Maya's own layout, with prefs/shelves/ and prefs/icons/
    - Python packages at the top
    - Maya modules: a .mod file, or a plug-ins/ folder

    With no shelf file, the buttons come from the shelfButton calls in the tool's Python code.
    """
    shelves = sorted({p for pattern in SHELF_GLOBS for p in glob.glob(os.path.join(folder, *pattern.split("/")))})
    icons_dir = next((d for d in ICON_DIRS if os.path.isdir(os.path.join(folder, *d.split("/")))), "")
    has_scripts = os.path.isdir(os.path.join(folder, "scripts"))
    loose = [] if has_scripts else root_scripts(folder) + root_packages(folder)
    module = bool(find_mod_files(folder)) or os.path.isdir(os.path.join(folder, "plug-ins"))
    if not (shelves or icons_dir or has_scripts or loose or module):
        return None
    name = os.path.basename(os.path.normpath(folder))
    tool = ToolInfo(
        id=slugify(name),
        name=name,
        description=("A Maya module. " if module else "") + "No easytool.json. Files were found by folder layout.",
        icons_dir=icons_dir,
        scripts_dir="scripts" if has_scripts else "",
        script_files=loose,
        shelf_files=[os.path.relpath(p, folder).replace("\\", "/") for p in shelves],
        has_manifest=False,
    )
    _find_module(folder, tool)
    images = find_images(folder) if module else {}
    if icons_dir:
        icons = os.path.join(folder, *icons_dir.split("/"))
        images.update((n, os.path.join(icons, n)) for n in os.listdir(icons) if n.lower().endswith(IMAGE_EXTS))
    if not shelves:
        tool.buttons = code_buttons(folder, sorted(images))
    preview = next((images[b.icon] for b in tool.buttons if b.icon in images), "")
    tool.preview_icon = preview or (images[min(images)] if images else "")
    return tool


def read_tool(folder: str):
    return load_manifest(folder) or scan_folder(folder)
