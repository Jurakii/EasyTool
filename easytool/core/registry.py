"""Record of what EasyTool installed, so updates and uninstalls touch only its own files."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .settings import read_json, write_json


@dataclass
class InstalledTool:
    id: str
    name: str
    version: str = ""
    category: str = "Utility"
    source_id: str = ""
    shelf: str = ""
    buttons: int = 0
    files: list = field(default_factory=list)  # paths EasyTool created
    backups: dict = field(default_factory=dict)  # original path -> where the user's file was moved
    shelf_files: list = field(default_factory=list)  # names of whole shelves this tool installed
    installed_at: str = ""


class Registry:
    def __init__(self, path: str):
        self.path = path
        self._tools = {}
        raw = read_json(path, {})
        for item in (raw.get("tools", []) if isinstance(raw, dict) else []):
            try:
                rec = InstalledTool(**item)
            except TypeError:
                continue
            self._tools[rec.id] = rec

    def get(self, tool_id: str):
        return self._tools.get(tool_id)

    def all(self) -> list:
        return list(self._tools.values())

    def put(self, rec: InstalledTool) -> None:
        self._tools[rec.id] = rec
        self.save()

    def remove(self, tool_id: str) -> None:
        self._tools.pop(tool_id, None)
        self.save()

    def save(self) -> None:
        write_json(self.path, {"tools": [asdict(t) for t in self._tools.values()]})
