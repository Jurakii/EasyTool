"""EasyTool's own settings, stored next to Maya's prefs in maya/easytool/settings.json.

Sources and the shelf name are shared by every Maya version. Folder choices and the record of
installed tools are kept per Maya version, because each version has its own prefs folders.
"""
from __future__ import annotations

import json
import os
import re

from .sources import Source, make_source

DEFAULT_FEED = "https://github.com/Jurakii/Tools"
SHELF_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def write_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    os.replace(tmp, path)


def read_json(path: str, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


class Settings:
    def __init__(self, root: str, default_sources=(DEFAULT_FEED,)):
        self.root = root
        self.path = os.path.join(root, "settings.json")
        self.data = {"sources": [], "folders": {}, "shelf": "EasyTool", "backup": True}
        if os.path.isfile(self.path):
            loaded = read_json(self.path, {})
            if isinstance(loaded, dict):
                self.data.update(loaded)
        else:  # first run: start with the default feed
            self.data["sources"] = [make_source(url).to_dict() for url in default_sources]

    @property
    def cache_dir(self) -> str:
        return os.path.join(self.root, "cache")

    @property
    def backup_dir(self) -> str:
        return os.path.join(self.root, "backups")

    def registry_path(self, version: str = "") -> str:
        """Where the record of installed tools lives: one file per Maya version."""
        return os.path.join(self.root, f"installed-{version}.json" if version else "installed.json")

    def save(self) -> None:
        write_json(self.path, self.data)

    # Sources

    @property
    def sources(self) -> list:
        out = []
        for raw in self.data.get("sources", []):
            try:
                out.append(Source(**{k: raw[k] for k in ("url", "kind", "name", "enabled") if k in raw}))
            except TypeError:
                continue
        return out

    def _store_sources(self, sources) -> None:
        self.data["sources"] = [s.to_dict() for s in sources]
        self.save()

    def add_source(self, source: Source) -> None:
        sources = self.sources
        if any(s.id == source.id for s in sources):
            raise ValueError("That source is already in the list.")
        sources.append(source)
        self._store_sources(sources)

    def remove_source(self, source_id: str) -> None:
        self._store_sources([s for s in self.sources if s.id != source_id])

    def set_source_enabled(self, source_id: str, enabled: bool) -> None:
        sources = self.sources
        for s in sources:
            if s.id == source_id:
                s.enabled = enabled
        self._store_sources(sources)

    @property
    def update_source(self):
        """The one source EasyTool takes updates of itself from."""
        try:
            return make_source(str(self.data.get("updateSource") or DEFAULT_FEED))
        except ValueError:
            return None

    # Folders (per Maya version) and shelf

    def folder_overrides(self, version: str) -> dict:
        folders = self.data.get("folders") or {}
        mine = folders.get(version or "any")
        if isinstance(mine, dict):
            return dict(mine)
        return {k: v for k, v in folders.items() if isinstance(v, str)}  # older settings: one set for every version

    def set_folder_override(self, version: str, kind: str, path: str) -> None:
        folders = {k: v for k, v in (self.data.get("folders") or {}).items() if isinstance(v, dict)}
        mine = self.folder_overrides(version)
        if path:
            mine[kind] = path
        else:
            mine.pop(kind, None)
        folders[version or "any"] = mine
        self.data["folders"] = folders
        self.save()

    @property
    def shelf(self) -> str:
        name = str(self.data.get("shelf") or "EasyTool")
        return name if SHELF_NAME.match(name) else "EasyTool"

    @shelf.setter
    def shelf(self, name: str) -> None:
        if not SHELF_NAME.match(name):
            raise ValueError("Shelf names can use letters, numbers and underscores, and can't start with a number.")
        self.data["shelf"] = name
        self.save()

    @property
    def backup(self) -> bool:
        return bool(self.data.get("backup", True))
