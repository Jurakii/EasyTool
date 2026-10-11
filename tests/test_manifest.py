import json
import os
import unittest

from helpers import EXAMPLES, TempDirTest, make_legacy_tool, make_module_tool

from easytool.core.manifest import ManifestError, load_manifest, parse_manifest, read_tool, scan_folder
from easytool.core.models import is_newer, slugify, version_key


class ParseManifestTest(unittest.TestCase):
    def test_full_manifest(self):
        tool = parse_manifest({
            "name": "Pivot Snap",
            "version": "2.1.0",
            "category": "modeling",
            "icons": "art/icons/",
            "buttons": [{"label": "PIV", "command": "print(1)", "doubleClick": "print(2)"}],
            "shelf": "shelves/shelf_Pivot.mel",
        })
        self.assertEqual(tool.id, "pivot-snap")
        self.assertEqual(tool.category, "Modeling")
        self.assertEqual(tool.icons_dir, "art/icons")
        self.assertEqual(tool.shelf_files, ["shelves/shelf_Pivot.mel"])
        self.assertEqual(tool.buttons[0].language, "python")
        self.assertEqual(tool.buttons[0].double_click, "print(2)")

    def test_name_falls_back_to_folder(self):
        tool = parse_manifest({}, fallback_name="My Tool")
        self.assertEqual((tool.id, tool.name), ("my-tool", "My Tool"))

    def test_fx_category_keeps_case(self):
        self.assertEqual(parse_manifest({"category": "fx"}).category, "FX")

    def test_rejects_bad_language(self):
        with self.assertRaisesRegex(ManifestError, "language"):
            parse_manifest({"buttons": [{"command": "x", "language": "lua"}]})

    def test_rejects_button_without_command(self):
        with self.assertRaisesRegex(ManifestError, "no command"):
            parse_manifest({"buttons": [{"label": "A"}]})

    def test_rejects_non_object(self):
        with self.assertRaises(ManifestError):
            parse_manifest([1, 2])


class FolderTest(TempDirTest):
    def test_example_manifest_has_preview_icon(self):
        tool = load_manifest(os.path.join(EXAMPLES, "pivot-snap"))
        self.assertEqual(len(tool.buttons), 3)
        self.assertTrue(tool.preview_icon.endswith("pivotSnap.png"))
        self.assertTrue(os.path.isfile(tool.preview_icon))

    def test_invalid_json_is_reported(self):
        self.write("bad/easytool.json", "{ nope")
        with self.assertRaisesRegex(ManifestError, "not valid JSON"):
            load_manifest(self.path("bad"))

    def test_scan_without_manifest(self):
        self.write("legacy/shelves/shelf_Legacy.mel", "global proc shelf_Legacy() {}")
        self.write("legacy/icons/legacy.png")
        tool = scan_folder(self.path("legacy"))
        self.assertFalse(tool.has_manifest)
        self.assertEqual(tool.shelf_files, ["shelves/shelf_Legacy.mel"])
        self.assertEqual(tool.scripts_dir, "")
        self.assertTrue(tool.preview_icon.endswith("legacy.png"))

    def test_scan_drag_into_prefs_layout(self):
        tool = scan_folder(make_legacy_tool(self.path("AssignRGB")))
        self.assertEqual(tool.script_files, ["AssignRGB.mel", "AssignRGBCMY.mel"])
        self.assertEqual(tool.shelf_files, ["shelves/shelf_ColorTools.mel"])
        self.assertEqual(tool.icons_dir, "icons")

    def test_empty_folder_is_not_a_tool(self):
        os.makedirs(self.path("empty"))
        self.assertIsNone(read_tool(self.path("empty")))


class LayoutTest(TempDirTest):
    def test_maya_module(self):
        tool = scan_folder(make_module_tool(self.path("Build")))
        self.assertTrue(tool.module)
        self.assertEqual((tool.mod_files, tool.version), (["build_modifier.mod"], "1.0"))
        [button] = tool.buttons  # from scripts/build_modifier/shelf.py; the one in tests/ is left out
        self.assertEqual((button.label, button.icon, button.language), ("Build", "buildModifier.png", "python"))
        self.assertTrue(tool.preview_icon.endswith("buildModifier.png"))

    def test_plug_ins_without_a_mod_file_are_a_module_too(self):
        self.write("Tool/plug-ins/toolNode.py")
        self.write("Tool/scripts/tool.py")
        tool = scan_folder(self.path("Tool"))
        self.assertEqual((tool.module, tool.mod_files), (True, []))

    def test_manifest_with_a_mod_file(self):
        make_module_tool(self.path("Build"))
        self.write("Build/easytool.json", json.dumps({"name": "Build", "version": "2.0"}))
        tool = load_manifest(self.path("Build"))
        self.assertEqual((tool.module, tool.version, tool.buttons), (True, "2.0", []))

    def test_python_package_at_the_top(self):
        self.write("Tool/my_tool/__init__.py")
        self.write("Tool/my_tool/ui.py")
        self.write("Tool/tests/__init__.py")
        self.write("Tool/easytool/__init__.py")
        self.write("Tool/install.py", 'cmds.shelfButton(label="MT", command="import my_tool; my_tool.show()", sourceType="python")')
        self.write("Tool/icons/myTool.png")
        self.write("Tool/icons/myTool_150.png")
        tool = scan_folder(self.path("Tool"))
        self.assertEqual(tool.script_files, ["my_tool"])
        [button] = tool.buttons  # from the installer, with the tool's only icon
        self.assertEqual((button.command, button.icon), ("import my_tool; my_tool.show()", "myTool.png"))

    def test_mayas_own_prefs_layout(self):
        self.write("Tool/scripts/tool.mel")
        self.write("Tool/prefs/icons/tool.png")
        self.write("Tool/prefs/shelves/shelf_Tool.mel", "global proc shelf_Tool() {}")
        tool = scan_folder(self.path("Tool"))
        self.assertEqual((tool.icons_dir, tool.scripts_dir), ("prefs/icons", "scripts"))
        self.assertEqual(tool.shelf_files, ["prefs/shelves/shelf_Tool.mel"])
        self.assertFalse(tool.module)


class VersionTest(unittest.TestCase):
    def test_numeric_compare(self):
        self.assertTrue(is_newer("1.10.0", "1.9.3"))
        self.assertTrue(is_newer("v2", "1.9"))
        self.assertFalse(is_newer("1.0", "1.0.0"))
        self.assertEqual(version_key(""), (0, 0, 0))

    def test_slugify(self):
        self.assertEqual(slugify("  UV Unfold Kit!! "), "uv-unfold-kit")
        self.assertEqual(slugify("***"), "tool")


if __name__ == "__main__":
    unittest.main()
