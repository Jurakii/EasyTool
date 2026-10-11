import json
import os
import unittest

from helpers import EXAMPLES, TempDirTest

from easytool.core.context import AppContext
from easytool.core.manifest import load_manifest
from easytool.core.paths import MayaFolders
from easytool.core.registry import InstalledTool, Registry
from easytool.core.settings import DEFAULT_FEED, Settings


class SettingsTest(TempDirTest):
    def test_first_run_starts_with_the_default_feed(self):
        settings = Settings(self.path("easytool"))
        [source] = settings.sources
        self.assertEqual((source.url, source.kind), (DEFAULT_FEED, "github"))
        settings.remove_source(source.id)
        self.assertEqual(Settings(self.path("easytool")).sources, [])  # not added back once the user removed it

    def test_update_source_defaults_to_the_feed(self):
        self.assertEqual(Settings(self.path("easytool"), default_sources=()).update_source.url, DEFAULT_FEED)

    def test_folder_choices_are_per_maya_version(self):
        settings = Settings(self.path("easytool"), default_sources=())
        settings.set_folder_override("2024", "icons", r"D:\icons24")
        reloaded = Settings(self.path("easytool"))
        self.assertEqual(reloaded.folder_overrides("2024"), {"icons": r"D:\icons24"})
        self.assertEqual(reloaded.folder_overrides("2025"), {})

    def test_older_shared_folder_choices_still_apply(self):
        settings = Settings(self.path("easytool"), default_sources=())
        settings.data["folders"] = {"icons": r"D:\shared"}
        self.assertEqual(settings.folder_overrides("2025"), {"icons": r"D:\shared"})


class PerVersionRecordTest(TempDirTest):
    def folders(self, version):
        base = self.path("maya", version)
        return MayaFolders(os.path.join(base, "prefs", "shelves"), os.path.join(base, "prefs", "icons"),
                           os.path.join(base, "scripts"), version)

    def context(self, version):
        return AppContext(app_dir=self.path("maya"), folders=self.folders(version), default_sources=())

    def test_install_in_2024_does_not_show_as_installed_in_2025(self):
        payload = os.path.join(EXAMPLES, "scene-cleaner")
        self.context("2024").installer().install(load_manifest(payload), payload)
        self.assertIsNotNone(self.context("2024").registry.get("scene-cleaner"))
        self.assertIsNone(self.context("2025").registry.get("scene-cleaner"))

    def test_old_shared_record_is_split_by_version(self):
        legacy = Registry(self.path("maya", "easytool", "installed.json"))
        f24, f25 = self.folders("2024"), self.folders("2025")
        legacy.put(InstalledTool(id="in-2024", name="A", files=[os.path.join(f24.icons, "a.png")]))
        legacy.put(InstalledTool(id="in-2025", name="B", files=[os.path.join(f25.scripts, "b.mel")]))
        self.assertEqual([r.id for r in self.context("2024").registry.all()], ["in-2024"])
        self.assertEqual([r.id for r in self.context("2025").registry.all()], ["in-2025"])
        with open(self.path("maya", "easytool", "installed-2024.json")) as fh:
            self.assertEqual([t["id"] for t in json.load(fh)["tools"]], ["in-2024"])


if __name__ == "__main__":
    unittest.main()
