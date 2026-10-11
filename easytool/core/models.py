"""Plain data objects shared by the core and the UI."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

CATEGORIES = ("Modeling", "Rigging", "Animation", "Lighting", "Rendering", "FX", "Pipeline", "Utility")
LANGUAGES = ("python", "mel")


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug or "tool"


def version_key(version: str) -> tuple:
    """Turn "v1.2.10" into (1, 2, 10) so versions compare numerically."""
    numbers = [int(n) for n in re.findall(r"\d+", version or "")]
    return tuple(numbers + [0] * max(0, 3 - len(numbers)))


def is_newer(candidate: str, current: str) -> bool:
    return version_key(candidate) > version_key(current)


@dataclass
class ButtonSpec:
    """One shelf button a tool asks for."""

    label: str = ""
    tooltip: str = ""
    icon: str = ""
    command: str = ""
    language: str = "python"
    double_click: str = ""
    overlay: str = ""  # text Maya draws over the icon

    @classmethod
    def from_dict(cls, data: dict) -> "ButtonSpec":
        return cls(**{k: data.get(k, getattr(cls, k)) for k in cls.__dataclass_fields__})

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Location:
    """Where a tool's files come from."""

    kind: str = "folder"  # "folder" | "zip" | "github"
    path: str = ""
    url: str = ""
    repo: str = ""  # "owner/name"
    ref: str = ""  # tag or branch; "" means the default branch
    subdir: str = ""


@dataclass
class ToolInfo:
    id: str
    name: str
    version: str = ""
    description: str = ""
    category: str = "Utility"
    author: str = ""
    maya: str = ""
    homepage: str = ""
    icon: str = ""
    icons_dir: str = "icons"
    scripts_dir: str = "scripts"
    script_files: list = field(default_factory=list)  # loose scripts, e.g. .mel files at the zip root
    shelf_files: list = field(default_factory=list)
    own_shelf: bool = False  # install shelf files as their own tabs instead of adding their buttons
    buttons: list = field(default_factory=list)
    has_manifest: bool = True
    location: Location = field(default_factory=Location)
    source_id: str = ""
    preview_icon: str = ""  # local image path the UI can show before installing

    @property
    def button_icons(self) -> list:
        return sorted({b.icon for b in self.buttons if b.icon})
