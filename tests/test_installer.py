import json
import os
import shutil
import unittest

from helpers import EXAMPLES, TempDirTest, make_legacy_tool

from easytool.core.installer import CANCEL, KEEP_BOTH, REPLACE, SKIP, Decision, InstallCancelled, InstallError, Installer
from easytool.core.manifest import load_manifest
from easytool.core.models import ToolInfo
from easytool.core.shelf import buttons_from_shelf_text
from easytool.core.paths import MayaFolders
from easytool.core.registry import Registry
from easytool.core.shelf import FileShelfBackend


class InstallerTest(TempDirTest):
    def setUp(self):
        super().setUp()
        self.folders = MayaFolders(self.path("prefs", "shelves"), self.path("prefs", "icons"), self.path("scripts"), "2024")
        for kind in ("shelves", "icons", "scripts"):
            os.makedirs(self.folders.get(kind))
        self.registry = Registry(self.path("easytool", "installed.json"))
        self.backend = FileShelfBackend(self.folders.shelves)
        self.installer = Installer(self.folders, self.registry, self.backend, self.path("easytool", "backups"))
        self.payload = self.path("payload", "pivot-snap")
        shutil.copytree(os.path.join(EXAMPLES, "pivot-snap"), self.payload)
        self.tool = load_manifest(self.payload)
        self.asked = []

    def answer(self, action, apply_to_all=False):
        def ask(conflict):
            self.asked.append(conflict)
            return Decision(action, apply_to_all)
        return ask

    def icon(self, name):
        return os.path.join(self.folders.icons, name)

    def blocks(self):
        return self.backend.button_blocks("EasyTool")

    def test_clean_install(self):
        rec = self.installer.install(self.tool, self.payload, ask=self.answer(CANCEL))
        self.assertEqual(self.asked, [])
        self.assertEqual(len(os.listdir(self.folders.icons)), 9)
        self.assertTrue(os.path.isfile(os.path.join(self.folders.scripts, "pivot_snap", "__init__.py")))
        self.assertEqual(len(self.blocks()), 3)
        self.assertIn('-docTag "easytool:pivot-snap"', self.blocks()[0])
        self.assertEqual((rec.version, rec.buttons, rec.shelf), ("1.0.0", 3, "EasyTool"))
        self.assertEqual(len(rec.files), 10)
        self.assertEqual(Registry(self.registry.path).get("pivot-snap").version, "1.0.0")

    def test_keep_both_renames_the_whole_icon_group(self):
        mine = self.write("prefs/icons/pivotSnap.png", b"mine")
        self.installer.install(self.tool, self.payload, ask=self.answer(KEEP_BOTH))
        self.assertEqual([c.name for c in self.asked], ["pivotSnap.png"])
        self.assertEqual(self.read(mine), b"mine")
        for name in ("pivotSnap_1.png", "pivotSnap_1_150.png", "pivotSnap_1_200.png"):
            self.assertTrue(os.path.isfile(self.icon(name)), name)
        self.assertFalse(os.path.exists(self.icon("pivotSnap_150.png")))
        self.assertIn('-image "pivotSnap_1.png"', self.blocks()[0])

    def test_replace_backs_up_and_uninstall_restores(self):
        self.write("prefs/icons/pivotSnap.png", b"mine")
        rec = self.installer.install(self.tool, self.payload, ask=self.answer(REPLACE))
        self.assertEqual(len(rec.backups), 1)
        self.assertNotEqual(self.read(self.icon("pivotSnap.png")), b"mine")

        self.installer.uninstall("pivot-snap")
        self.assertEqual(self.read(self.icon("pivotSnap.png")), b"mine")
        self.assertEqual(os.listdir(self.folders.icons), ["pivotSnap.png"])
        self.assertEqual(os.listdir(self.folders.scripts), [])
        self.assertEqual(self.blocks(), [])
        self.assertIsNone(self.registry.get("pivot-snap"))

    def test_cancel_rolls_everything_back(self):
        self.write("scripts/pivot_snap/__init__.py", "# someone else's module")
        with self.assertRaises(InstallCancelled):
            self.installer.install(self.tool, self.payload, ask=self.answer(CANCEL))
        self.assertEqual(os.listdir(self.folders.icons), [])
        self.assertEqual(self.read(os.path.join(self.folders.scripts, "pivot_snap", "__init__.py")), b"# someone else's module")
        self.assertFalse(os.path.exists(self.backend.path("EasyTool")))
        self.assertIsNone(self.registry.get("pivot-snap"))

    def test_skip_keeps_users_script(self):
        self.write("scripts/pivot_snap/__init__.py", "# mine")
        rec = self.installer.install(self.tool, self.payload, ask=self.answer(SKIP))
        self.assertEqual(self.asked[0].kind, "script")
        self.assertFalse(self.asked[0].can_keep_both)
        self.assertEqual(self.read(os.path.join(self.folders.scripts, "pivot_snap", "__init__.py")), b"# mine")
        self.assertNotIn(os.path.join(self.folders.scripts, "pivot_snap"), rec.files)

    def test_identical_files_are_not_conflicts(self):
        shutil.copy(os.path.join(self.payload, "icons", "pivotSnap.png"), self.icon("pivotSnap.png"))
        rec = self.installer.install(self.tool, self.payload, ask=self.answer(CANCEL))
        self.assertEqual(self.asked, [])
        self.assertNotIn(self.icon("pivotSnap.png"), rec.files)

    def test_update_replaces_own_files_without_asking(self):
        self.installer.install(self.tool, self.payload)
        manifest_path = os.path.join(self.payload, "easytool.json")
        with open(manifest_path) as fh:
            data = json.load(fh)
        data["version"] = "1.1.0"
        data["buttons"] = data["buttons"][:2]
        with open(manifest_path, "w") as fh:
            json.dump(data, fh)
        for suffix in ("", "_150", "_200"):
            os.remove(os.path.join(self.payload, "icons", f"pivotSnapOrigin{suffix}.png"))

        rec = self.installer.install(load_manifest(self.payload), self.payload, ask=self.answer(CANCEL))
        self.assertEqual(self.asked, [])
        self.assertEqual(rec.version, "1.1.0")
        self.assertEqual(len(self.blocks()), 2)
        self.assertFalse(os.path.exists(self.icon("pivotSnapOrigin.png")))
        self.assertEqual(len(os.listdir(self.folders.icons)), 6)

    def test_mel_tool(self):
        payload = os.path.join(EXAMPLES, "scene-cleaner")
        self.installer.install(load_manifest(payload), payload)
        self.assertTrue(os.path.isfile(os.path.join(self.folders.scripts, "sceneCleaner.mel")))
        self.assertIn('-sourceType "mel"', self.blocks()[0])

    def test_drag_into_prefs_zip_puts_its_buttons_on_the_chosen_shelf(self):
        payload = make_legacy_tool(self.path("payload", "colors"))
        listed = ToolInfo(id="assign-rgb", name="Assign RGB", version="1.0.0")  # as a feed lists it
        rec = self.installer.install(listed, payload)
        blocks = self.blocks()
        self.assertEqual(len(blocks), 2)
        self.assertIn('-docTag "easytool:assign-rgb"', blocks[0])
        self.assertEqual(buttons_from_shelf_text(blocks[0])[0].command.splitlines()[1], 'if (!`objExists "R"`) {')
        self.assertFalse(os.path.exists(os.path.join(self.folders.shelves, "shelf_ColorTools.mel")))
        self.assertEqual(sorted(os.listdir(self.folders.scripts)), ["AssignRGB.mel", "AssignRGBCMY.mel"])
        self.assertEqual(sorted(os.listdir(self.folders.icons)), ["AssignRGB.png", "Second.png"])
        self.assertEqual((rec.name, rec.version, rec.buttons), ("Assign RGB", "1.0.0", 2))

    def test_own_shelf_installs_the_shelf_file_as_a_tab(self):
        payload = make_legacy_tool(self.path("payload", "colors"))
        listed = ToolInfo(id="assign-rgb", name="Assign RGB", version="1.0.0", own_shelf=True)
        rec = self.installer.install(listed, payload)
        self.assertTrue(os.path.isfile(os.path.join(self.folders.shelves, "shelf_ColorTools.mel")))
        self.assertFalse(os.path.exists(self.backend.path("EasyTool")))
        self.assertEqual((rec.shelf_files, rec.shelf), (["ColorTools"], ""))

    def test_nothing_to_install(self):
        empty = self.path("payload", "empty")
        self.write("payload/empty/easytool.json", json.dumps({"name": "Empty"}))
        with self.assertRaises(InstallError):
            self.installer.install(load_manifest(empty), empty)


if __name__ == "__main__":
    unittest.main()
