import json
import os
import shutil
import unittest
from unittest import mock

from helpers import EXAMPLES, TempDirTest, make_legacy_tool, make_module_tool

from easytool.core import installer as installer_module
from easytool.core.installer import CANCEL, KEEP_BOTH, REPLACE, SKIP, Decision, InstallCancelled, InstallError, Installer
from easytool.core.manifest import load_manifest, read_tool
from easytool.core.models import ToolInfo
from easytool.core.shelf import buttons_from_shelf_text
from easytool.core.paths import MayaFolders
from easytool.core.registry import Registry
from easytool.core.shelf import FileShelfBackend


class InstallerCase(TempDirTest):
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


class InstallerTest(InstallerCase):
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

    def test_python_package_at_the_top_goes_to_scripts(self):
        self.write("payload/tool/my_tool/__init__.py", "")
        self.write("payload/tool/README.md")
        payload = self.path("payload", "tool")
        self.installer.install(read_tool(payload), payload)
        self.assertEqual(os.listdir(self.folders.scripts), ["my_tool"])
        self.assertTrue(os.path.isfile(os.path.join(self.folders.scripts, "my_tool", "__init__.py")))


class ModuleInstallTest(InstallerCase):
    def setUp(self):
        super().setUp()
        self.module_payload = make_module_tool(self.path("payload", "Build"))
        self.listed = ToolInfo(id="build", name="Build", version="1.0")  # as a feed lists it
        self.modules = self.folders.modules

    def mod_text(self, name="build_modifier.mod"):
        with open(os.path.join(self.modules, name)) as fh:
            return fh.read()

    def test_installs_the_folder_whole_with_its_mod_file(self):
        rec = self.installer.install(self.listed, self.module_payload, ask=self.answer(CANCEL))
        folder = os.path.join(self.modules, "build_modifier")
        self.assertEqual(self.mod_text(), "+ build_modifier 1.0 ./build_modifier\n")
        for rel in ("scripts/build_modifier/shelf.py", "plug-ins/buildModifierNode.py", "icons/buildModifier.png", "install_drop.py"):
            self.assertTrue(os.path.isfile(os.path.join(folder, *rel.split("/"))), rel)
        self.assertFalse(os.path.exists(os.path.join(folder, "build_modifier.mod")))
        self.assertFalse(os.path.exists(os.path.join(folder, ".gitattributes")))
        self.assertEqual((os.listdir(self.folders.scripts), os.listdir(self.folders.icons)), ([], []))
        self.assertEqual(sorted(rec.files), sorted([folder, os.path.join(self.modules, "build_modifier.mod")]))

        [block] = self.blocks()
        icon = os.path.join(folder, "icons", "buildModifier.png").replace("\\", "/")
        self.assertIn(f'-image "{icon}"', block)  # Maya finds a new module's icons by name only after a restart
        self.assertIn('-docTag "easytool:build"', block)
        self.assertIn('-sourceType "python"', block)

        self.installer.uninstall("build")
        self.assertEqual(os.listdir(self.modules), [])
        self.assertEqual(self.blocks(), [])

    def test_update_replaces_the_module_without_asking(self):
        self.installer.install(self.listed, self.module_payload)
        self.write("payload/Build/scripts/build_modifier/new.py", "")
        os.remove(os.path.join(self.module_payload, "README.md"))
        self.installer.install(ToolInfo(id="build", name="Build", version="1.1"), self.module_payload, ask=self.answer(CANCEL))
        folder = os.path.join(self.modules, "build_modifier")
        self.assertEqual(self.asked, [])
        self.assertTrue(os.path.isfile(os.path.join(folder, "scripts", "build_modifier", "new.py")))
        self.assertFalse(os.path.exists(os.path.join(folder, "README.md")))
        self.assertEqual(len(self.blocks()), 1)

    def test_replacing_the_users_mod_file_backs_it_up(self):
        mine = self.write("modules/build_modifier.mod", "+ build_modifier 1.0 C:/dev/Build\n")
        self.installer.install(self.listed, self.module_payload, ask=self.answer(REPLACE))
        self.assertEqual([(c.kind, c.name) for c in self.asked], [("module", "build_modifier.mod")])
        self.assertIn("./build_modifier", self.mod_text())
        self.installer.uninstall("build")
        self.assertEqual(self.read(mine), b"+ build_modifier 1.0 C:/dev/Build\n")
        self.assertEqual(os.listdir(self.modules), ["build_modifier.mod"])

    def test_skipping_the_users_module_folder_writes_no_mod_file(self):
        self.write("modules/build_modifier/scripts/mine.py", "# mine")
        rec = self.installer.install(self.listed, self.module_payload, ask=self.answer(SKIP))
        self.assertEqual([(c.kind, c.name) for c in self.asked], [("module", "build_modifier")])
        self.assertEqual(os.listdir(self.modules), ["build_modifier"])
        self.assertEqual(os.listdir(os.path.join(self.modules, "build_modifier", "scripts")), ["mine.py"])
        self.assertEqual(rec.files, [])

    def test_plug_ins_without_a_mod_file_get_one(self):
        self.write("payload/Loose/looseTool.py", "")
        self.write("payload/Loose/plug-ins/looseNode.py", "")
        payload = self.path("payload", "Loose")
        self.installer.install(ToolInfo(id="loose", name="Loose", version="2.0"), payload)
        self.assertEqual(self.mod_text("loose.mod"), "+ loose 2.0 ./loose\nscripts: .\n")
        self.assertTrue(os.path.isfile(os.path.join(self.modules, "loose", "plug-ins", "looseNode.py")))
        self.assertEqual(os.listdir(self.folders.scripts), [])

    def test_module_in_use_is_left_alone(self):
        self.installer.install(self.listed, self.module_payload)
        before = self.mod_text()
        with mock.patch.object(installer_module.os, "rename", side_effect=PermissionError(13, "Access is denied")):
            with self.assertRaisesRegex(InstallError, "loaded plug-in"):
                self.installer.install(ToolInfo(id="build", name="Build", version="1.1"), self.module_payload)
        self.assertEqual((self.mod_text(), self.registry.get("build").version), (before, "1.0"))
        self.assertTrue(os.path.isfile(os.path.join(self.modules, "build_modifier", "plug-ins", "buildModifierNode.py")))

    def test_files_in_use_keep_the_record_so_removing_again_finishes(self):
        self.installer.install(self.listed, self.module_payload)
        folder = os.path.join(self.modules, "build_modifier")
        real_delete = installer_module._delete
        with mock.patch.object(installer_module, "_delete", lambda p: None if p == folder else real_delete(p)):
            with self.assertRaisesRegex(InstallError, "in use"):
                self.installer.uninstall("build")
        self.assertEqual(self.registry.get("build").files, [folder])
        self.assertEqual(self.blocks(), [])
        self.installer.uninstall("build")
        self.assertEqual(os.listdir(self.modules), [])
        self.assertIsNone(self.registry.get("build"))


if __name__ == "__main__":
    unittest.main()
