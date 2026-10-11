"""Read easytool.json, or work out a tool from its folder layout when there is none."""
from __future__ import annotations

import glob
import json
import os

from .models import CATEGORIES, LANGUAGES, ButtonSpec, ToolInfo, slugify

MANIFEST_NAME = "easytool.json"
INDEX_NAME = "index.json"
IMAGE_EXTS = (".png", ".svg", ".xpm", ".jpg", ".jpeg", ".bmp", ".gif")
SCRIPT_EXTS = (".mel", ".py")
NOT_TOOL_SCRIPTS = ("usersetup.py", "usersetup.mel", "setup.py", "__init__.py")


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
    tool.preview_icon = find_preview_icon(folder, tool)
    return tool


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


def scan_folder(folder: str):
    """Build a tool from a folder with no manifest: shelves/, icons/, and scripts/ or loose scripts."""
    shelves = sorted(set(
        glob.glob(os.path.join(folder, "shelves", "shelf_*.mel"))
        + glob.glob(os.path.join(folder, "shelf_*.mel"))
    ))
    has_icons = os.path.isdir(os.path.join(folder, "icons"))
    has_scripts = os.path.isdir(os.path.join(folder, "scripts"))
    loose = [] if has_scripts else root_scripts(folder)
    if not (shelves or has_icons or has_scripts or loose):
        return None
    name = os.path.basename(os.path.normpath(folder))
    tool = ToolInfo(
        id=slugify(name),
        name=name,
        description="No easytool.json. Files were found by folder layout.",
        icons_dir="icons" if has_icons else "",
        scripts_dir="scripts" if has_scripts else "",
        script_files=loose,
        shelf_files=[os.path.relpath(p, folder).replace("\\", "/") for p in shelves],
        has_manifest=False,
    )
    if has_icons:
        images = sorted(f for f in os.listdir(os.path.join(folder, "icons")) if f.lower().endswith(IMAGE_EXTS))
        if images:
            tool.preview_icon = os.path.join(folder, "icons", images[0])
    return tool


def read_tool(folder: str):
    return load_manifest(folder) or scan_folder(folder)
