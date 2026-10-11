"""Add and remove shelf buttons.

Inside Maya the live shelf is edited with maya.cmds and then saved, because Maya rewrites
every loaded shelf file when it quits; editing the .mel file behind its back would be undone.
Outside Maya (tests, previews) the .mel file is edited directly.

Every button EasyTool creates carries docTag "easytool:<tool id>" so it can be found again.
"""
from __future__ import annotations

import importlib
import os
import re

from .models import LANGUAGES, ButtonSpec

TAG_PREFIX = "easytool:"
DEFAULT_ICON = "commandButton.png"
LABEL_COLOR = (0.93, 0.91, 0.87)
LABEL_BACK = (0.0, 0.0, 0.0, 0.5)


def tool_tag(tool_id: str) -> str:
    return TAG_PREFIX + tool_id


def shelf_name_from_file(path: str) -> str:
    base = os.path.splitext(os.path.basename(path))[0]
    return base[len("shelf_"):] if base.startswith("shelf_") else base


def mel_string(text: str) -> str:
    escaped = (
        (text or "")
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r\n", "\n")
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


def mel_unescape(text: str) -> str:
    escapes = {"n": "\n", "t": "\t", "r": "\r"}
    return re.sub(r"\\(.)", lambda m: escapes.get(m.group(1), m.group(1)), text, flags=re.DOTALL)


def _floats(values) -> str:
    return " ".join(f"{v:g}" for v in values)


def overlay_text(button) -> str:
    """Text drawn over the icon: the button's own overlay, or its label when it has no icon."""
    return button.overlay or ("" if button.icon else button.label)


def button_mel(button, tag: str) -> str:
    image = button.icon or DEFAULT_ICON
    lines = [
        "    shelfButton",
        "        -enableCommandRepeat 1",
        f"        -label {mel_string(button.label or button.tooltip or 'Tool')}",
        f"        -annotation {mel_string(button.tooltip or button.label)}",
    ]
    if overlay_text(button):
        lines += [
            f"        -imageOverlayLabel {mel_string(overlay_text(button))}",
            f"        -overlayLabelColor {_floats(LABEL_COLOR)}",
            f"        -overlayLabelBackColor {_floats(LABEL_BACK)}",
        ]
    lines += [
        f"        -image {mel_string(image)}",
        f"        -image1 {mel_string(image)}",
        '        -style "iconOnly"',
        f"        -docTag {mel_string(tag)}",
        f"        -command {mel_string(button.command)}",
        f"        -sourceType {mel_string(button.language)}",
    ]
    if button.double_click:
        lines.append(f"        -doubleClickCommand {mel_string(button.double_click)}")
    lines.append("    ;")
    return "\n".join(lines)


def shelf_file_text(name: str, blocks) -> str:
    body = "\n".join(b.rstrip("\n") for b in blocks)
    return (
        f"global proc shelf_{name} () {{\n"
        "    global string $gBuffStr;\n"
        "    global string $gBuffStr0;\n"
        "    global string $gBuffStr1;\n\n"
        f"{body}\n\n"
        "}\n"
    )


BLOCK = re.compile(r"^[ \t]*shelfButton\b.*?^[ \t]*;[ \t]*$\n?", re.MULTILINE | re.DOTALL)
MEL_STRING = r'"((?:[^"\\]|\\.)*)"'


def _flag(block: str, name: str) -> str:
    match = re.search(r"-" + name + r"\s+" + MEL_STRING, block, re.DOTALL)
    return mel_unescape(match.group(1)) if match else ""


def _blocks(text: str) -> list:
    return BLOCK.findall(text.replace("\r\n", "\n").replace("\r", "\n"))


def buttons_from_shelf_text(text: str) -> list:
    """Read the buttons out of a shelf_<name>.mel file, as Maya writes them."""
    buttons = []
    for block in _blocks(text):
        command = _flag(block, "command")
        if not command:
            continue
        language = (_flag(block, "sourceType") or "mel").lower()
        buttons.append(ButtonSpec(
            label=_flag(block, "label"),
            tooltip=_flag(block, "annotation"),
            icon=_flag(block, "image") or _flag(block, "image1"),
            command=command,
            language=language if language in LANGUAGES else "mel",
            double_click=_flag(block, "doubleClickCommand"),
            overlay=_flag(block, "imageOverlayLabel"),
        ))
    return buttons


def read_shelf_file(path: str) -> list:
    with open(path, "rb") as fh:
        data = fh.read()
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:  # Maya on Windows may save in the system code page
        text = data.decode("cp1252", errors="replace")
    return buttons_from_shelf_text(text)


class FileShelfBackend:
    """Edits shelf_<name>.mel files directly. Used when Maya isn't running."""

    def __init__(self, shelves_dir: str):
        self.shelves_dir = shelves_dir

    def path(self, name: str) -> str:
        return os.path.join(self.shelves_dir, f"shelf_{name}.mel")

    def _read_blocks(self, name: str) -> list:
        try:
            with open(self.path(name), encoding="utf-8") as fh:
                return _blocks(fh.read())
        except OSError:
            return []

    def _write(self, name: str, blocks) -> None:
        os.makedirs(self.shelves_dir, exist_ok=True)
        with open(self.path(name), "w", encoding="utf-8") as fh:
            fh.write(shelf_file_text(name, blocks))

    def list_shelves(self) -> list:
        if not os.path.isdir(self.shelves_dir):
            return []
        return sorted(
            shelf_name_from_file(f) for f in os.listdir(self.shelves_dir)
            if f.startswith("shelf_") and f.endswith(".mel")
        )

    def ensure_shelf(self, name: str) -> None:
        if not os.path.isfile(self.path(name)):
            self._write(name, [])

    def button_blocks(self, name: str) -> list:
        return self._read_blocks(name)

    def add_buttons(self, name: str, buttons, tag: str) -> None:
        self._write(name, self._read_blocks(name) + [button_mel(b, tag) for b in buttons])

    def remove_buttons(self, name: str, tag: str) -> int:
        if not os.path.isfile(self.path(name)):
            return 0
        marker = re.compile(r"-docTag\s+" + re.escape(mel_string(tag)) + r"\s")
        blocks = self._read_blocks(name)
        kept = [b for b in blocks if not marker.search(b)]
        if len(kept) != len(blocks):
            self._write(name, kept)
        return len(blocks) - len(kept)

    def save(self, name: str) -> None:
        pass

    def select(self, name: str) -> None:
        pass

    def load_shelf_file(self, path: str) -> None:
        pass

    def remove_shelf(self, name: str) -> None:
        pass

    def refresh_scripts(self) -> None:
        importlib.invalidate_caches()


class MayaShelfBackend:
    """Edits shelves in the running Maya session, then saves them to disk."""

    def __init__(self, shelves_dir: str):
        from maya import cmds, mel
        self.cmds, self.mel = cmds, mel
        self.shelves_dir = shelves_dir

    def _top(self) -> str:
        return self.mel.eval("$easyToolTmp = $gShelfTopLevel")

    def _fwd(self, path: str) -> str:
        return path.replace("\\", "/")

    def list_shelves(self) -> list:
        return list(self.cmds.shelfTabLayout(self._top(), query=True, childArray=True) or [])

    def _load_contents(self, name: str) -> None:
        """Maya builds a shelf's buttons only when its tab is first opened. Load them before
        reading, editing or saving the shelf, or saving would write it out empty."""
        count = int(self.cmds.optionVar(query="numShelves") or 0)
        for index in range(1, count + 1):
            if self.cmds.optionVar(query=f"shelfName{index}") == name:
                self.mel.eval(f"loadShelf {index}")
                return

    def ensure_shelf(self, name: str) -> None:
        if self.cmds.shelfLayout(name, exists=True):
            self._load_contents(name)
            return
        path = os.path.join(self.shelves_dir, f"shelf_{name}.mel")
        if os.path.isfile(path):
            self.mel.eval(f'loadNewShelf "{self._fwd(path)}"')
        else:
            self.mel.eval(f'addNewShelfTab "{name}"')

    def _buttons(self, name: str) -> list:
        if not self.cmds.shelfLayout(name, exists=True):
            return []
        self._load_contents(name)
        parent = self.cmds.shelfLayout(name, query=True, fullPathName=True)
        out = []
        for child in self.cmds.shelfLayout(name, query=True, childArray=True) or []:
            full = f"{parent}|{child}"
            if self.cmds.objectTypeUI(full) == "shelfButton":
                out.append(full)
        return out

    def add_buttons(self, name: str, buttons, tag: str) -> None:
        for b in buttons:
            kwargs = dict(
                parent=name,
                label=b.label or b.tooltip or "Tool",
                annotation=b.tooltip or b.label,
                image=b.icon or DEFAULT_ICON,
                image1=b.icon or DEFAULT_ICON,
                style="iconOnly",
                command=b.command,
                sourceType=b.language,
                docTag=tag,
                enableCommandRepeat=True,
            )
            if overlay_text(b):
                kwargs.update(imageOverlayLabel=overlay_text(b), overlayLabelColor=LABEL_COLOR, overlayLabelBackColor=LABEL_BACK)
            if b.double_click:
                kwargs["doubleClickCommand"] = b.double_click
            self.cmds.shelfButton(**kwargs)

    def remove_buttons(self, name: str, tag: str) -> int:
        removed = 0
        for button in self._buttons(name):
            if self.cmds.shelfButton(button, query=True, docTag=True) == tag:
                self.cmds.deleteUI(button)
                removed += 1
        return removed

    def save(self, name: str) -> None:
        if not self.cmds.shelfLayout(name, exists=True):
            return
        self._load_contents(name)
        base = os.path.join(self.shelves_dir, f"shelf_{name}")
        os.makedirs(self.shelves_dir, exist_ok=True)
        self.cmds.saveShelf(name, self._fwd(base))
        if os.path.isfile(base) and not os.path.isfile(base + ".mel"):
            os.replace(base, base + ".mel")

    def select(self, name: str) -> None:
        if self.cmds.shelfLayout(name, exists=True):
            self.cmds.shelfTabLayout(self._top(), edit=True, selectTab=name)

    def load_shelf_file(self, path: str) -> None:
        name = shelf_name_from_file(path)
        if self.cmds.shelfLayout(name, exists=True):
            self.cmds.deleteUI(name, layout=True)
        self.mel.eval(f'loadNewShelf "{self._fwd(path)}"')

    def remove_shelf(self, name: str) -> None:
        if self.cmds.shelfLayout(name, exists=True):
            self.cmds.deleteUI(name, layout=True)

    def refresh_scripts(self) -> None:
        importlib.invalidate_caches()
        self.mel.eval("rehash")
