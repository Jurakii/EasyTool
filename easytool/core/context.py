"""Wires settings, folders, registry, resolver and shelf backend together for the UI."""
from __future__ import annotations

import os

from .installer import Installer
from .paths import FOLDER_KINDS, apply_overrides, default_app_dir, detect_maya_folders, maya_cmds
from .registry import Registry
from .settings import DEFAULT_FEED, Settings
from .shelf import FileShelfBackend, MayaShelfBackend
from .sources import Resolver


def _under(path: str, folder: str) -> bool:
    folder = os.path.normcase(os.path.normpath(folder))
    return os.path.normcase(os.path.normpath(path)).startswith(folder + os.sep)


class AppContext:
    def __init__(self, app_dir: str = None, folders=None, backend=None, http=None, default_sources=(DEFAULT_FEED,)):
        self.app_dir = app_dir or default_app_dir()
        self.settings = Settings(os.path.join(self.app_dir, "easytool"), default_sources)
        self.in_maya = maya_cmds() is not None
        self.detected_folders = folders or detect_maya_folders(self.app_dir)
        self.version = self.detected_folders.version
        self.folders = apply_overrides(self.detected_folders, self.settings.folder_overrides(self.version))
        self.registry = self._open_registry()
        self.resolver = Resolver(self.settings.cache_dir, http)
        self._backend_override = backend
        self._backend = None

    def _open_registry(self) -> Registry:
        path = self.settings.registry_path(self.version)
        registry = Registry(path)
        legacy = self.settings.registry_path("")
        if self.version and not os.path.exists(path) and os.path.exists(legacy):
            # Older EasyTool kept one record for every Maya version: keep only what lives in this version's folders.
            folders = [self.folders.get(kind) for kind in FOLDER_KINDS]
            for rec in Registry(legacy).all():
                if any(_under(f, folder) for f in rec.files for folder in folders):
                    registry.put(rec)
        return registry

    @property
    def backend(self):
        if self._backend_override is not None:
            return self._backend_override
        if self._backend is None or self._backend.shelves_dir != self.folders.shelves:
            backend_cls = MayaShelfBackend if self.in_maya else FileShelfBackend
            self._backend = backend_cls(self.folders.shelves)
        return self._backend

    def set_folder(self, kind: str, path: str) -> None:
        detected = self.detected_folders.get(kind)
        same = path and os.path.normcase(os.path.normpath(path)) == os.path.normcase(os.path.normpath(detected))
        self.settings.set_folder_override(self.version, kind, "" if (not path or same) else path)
        self.folders = apply_overrides(self.detected_folders, self.settings.folder_overrides(self.version))

    def installer(self) -> Installer:
        return Installer(
            self.folders,
            self.registry,
            self.backend,
            self.settings.backup_dir,
            shelf=self.settings.shelf,
            keep_backups=self.settings.backup,
        )
