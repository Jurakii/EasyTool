import os
import unittest

from helpers import TempDirTest

from easytool.core.modules import find_mod_files, folder_name, module_text, parse_mod, rewrite_mod, session_paths

MULTI = """\
# one module, built for two Maya versions
+ MAYAVERSION:2024 PLATFORM:win64 mytool 2.0 ./platforms/2024
PYTHONPATH+:=scripts/site-packages
MYTOOL_LICENSE=server@27000

- MAYAVERSION:2025 mytool 2.0 ./platforms/2025
"""


class ParseTest(unittest.TestCase):
    def test_sections(self):
        first, second = parse_mod(MULTI)
        self.assertEqual((first.name, first.version, first.path), ("mytool", "2.0", "./platforms/2024"))
        self.assertEqual((first.maya, first.platform, first.enabled), ("2024", "win64", True))
        self.assertEqual(first.lines, ["PYTHONPATH+:=scripts/site-packages", "MYTOOL_LICENSE=server@27000"])
        self.assertFalse(second.enabled)
        self.assertTrue(first.applies("2024", "win64"))
        self.assertFalse(first.applies("2025", "win64"))
        self.assertFalse(first.applies("2024", "linux"))

    def test_rewrite_points_into_the_copied_folder(self):
        text = rewrite_mod(MULTI, "unused", "mytool")
        self.assertIn("+ MAYAVERSION:2024 PLATFORM:win64 mytool 2.0 ./mytool/platforms/2024\n", text)
        self.assertIn("- MAYAVERSION:2025 mytool 2.0 ./mytool/platforms/2025\n", text)
        self.assertIn("PYTHONPATH+:=scripts/site-packages\n", text)
        self.assertIn("# one module", text)
        self.assertEqual(rewrite_mod("+ build_modifier 1.0 .", "unused", "build_modifier"), "+ build_modifier 1.0 ./build_modifier\n")
        self.assertEqual(rewrite_mod("+ a 1.0 sub\\dir\\", "unused", "a"), "+ a 1.0 ./a/sub/dir\n")


class RewriteTest(TempDirTest):
    def test_paths_from_the_authors_machine(self):
        os.makedirs(self.path("tool", "MyTool"))
        self.assertEqual(rewrite_mod("+ MyTool 1.0 C:/Users/author/maya/modules/MyTool", self.path("tool"), "MyTool"),
                         "+ MyTool 1.0 ./MyTool/MyTool\n")
        self.assertEqual(rewrite_mod("+ Other 1.0 D:\\dev\\Other", self.path("tool"), "Other"), "+ Other 1.0 ./Other\n")
        self.assertEqual(rewrite_mod("+ Up 1.0 ../elsewhere", self.path("tool"), "Up"), "+ Up 1.0 ./Up\n")

    def test_names(self):
        self.write("tool/b.mod", "+ b 1 .")
        self.write("tool/a.MOD", "+ a 1 .")
        self.write("tool/notes.txt")
        self.assertEqual(find_mod_files(self.path("tool")), ["a.MOD", "b.mod"])
        self.assertEqual(folder_name(["My Tool.mod"], "my-tool"), "My_Tool")
        self.assertEqual(folder_name([], "pivot-snap"), "pivot-snap")
        self.assertEqual(module_text("pivot-snap", "", "pivot-snap"), "+ pivot_snap 1.0 ./pivot-snap\n")
        self.assertEqual(module_text("t", "2.1", "t", ["scripts: ."]), "+ t 2.1 ./t\nscripts: .\n")


class SessionPathsTest(TempDirTest):
    def test_folders_that_exist(self):
        for rel in ("mods/tool/scripts", "mods/tool/plug-ins", "mods/tool/icons"):
            os.makedirs(self.path(*rel.split("/")))
        mod = self.write("mods/tool.mod", "+ tool 1.0 ./tool\n")
        root = self.path("mods", "tool")
        self.assertEqual(session_paths(mod, "2024", "win64"), [
            ("MAYA_SCRIPT_PATH", os.path.join(root, "scripts"), True),
            ("PYTHONPATH", os.path.join(root, "scripts"), True),
            ("MAYA_PLUG_IN_PATH", os.path.join(root, "plug-ins"), True),
            ("XBMLANGPATH", os.path.join(root, "icons"), True),
        ])

    def test_matching_section_and_its_lines(self):
        os.makedirs(self.path("mods", "t", "src"))
        mod = self.write("mods/t.mod", (
            "+ MAYAVERSION:2025 t 1.0 ./elsewhere\n"
            "+ MAYAVERSION:2024 t 1.0 ./t\n"
            "[r] scripts: src\n"
            "PYTHONPATH +:= lib\n"
            "T_LICENSE = server@27000\n"
            "+ MAYAVERSION:2024 t 1.0 ./second-match-is-ignored\n"
        ))
        root = self.path("mods", "t")
        self.assertEqual(session_paths(mod, "2024", "win64"), [
            ("MAYA_SCRIPT_PATH", os.path.join(root, "src"), True),
            ("PYTHONPATH", os.path.join(root, "src"), True),
            ("PYTHONPATH", os.path.join(root, "lib"), True),
            ("T_LICENSE", "server@27000", False),
        ])
        self.assertEqual(session_paths(mod, "2023", "win64"), [])


if __name__ == "__main__":
    unittest.main()
