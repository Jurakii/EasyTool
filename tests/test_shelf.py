import unittest

from helpers import LEGACY_SHELF, MODULE_SHELF_PY, TempDirTest

from easytool.core.models import ButtonSpec
from easytool.core.shelf import (
    FileShelfBackend, button_mel, buttons_from_python_text, buttons_from_shelf_text, mel_string, tool_tag,
)

USER_BLOCK = """    shelfButton
        -label "Mine"
        -command "print('mine')"
        -sourceType "python"
    ;
"""


class MelTest(unittest.TestCase):
    def test_escaping(self):
        self.assertEqual(mel_string('print("a\\b")\nx'), '"print(\\"a\\\\b\\")\\nx"')

    def test_overlay_label_only_without_icon(self):
        with_icon = button_mel(ButtonSpec(label="PIV", icon="p.png", command="x"), "easytool:p")
        without = button_mel(ButtonSpec(label="PIV", command="x"), "easytool:p")
        self.assertNotIn("imageOverlayLabel", with_icon)
        self.assertIn('-imageOverlayLabel "PIV"', without)
        self.assertIn('-image "commandButton.png"', without)


class ShelfFileTest(unittest.TestCase):
    def test_reads_buttons_from_a_maya_shelf_file(self):
        rgb, second = buttons_from_shelf_text(LEGACY_SHELF)
        self.assertEqual((rgb.label, rgb.tooltip, rgb.icon, rgb.language),
                         ("Assign RGB", "Assign RGB Standard Surface", "AssignRGB.png", "mel"))
        self.assertEqual(rgb.command, '// Assign RGB\nif (!`objExists "R"`) {\n\tshadingNode -asShader standardSurface -name "R";\n}')
        self.assertEqual((second.language, second.overlay, second.command), ("python", "2nd", 'print("hi")'))

    def test_windows_line_endings(self):
        self.assertEqual(buttons_from_shelf_text(LEGACY_SHELF.replace("\n", "\r\n")), buttons_from_shelf_text(LEGACY_SHELF))

    def test_round_trip(self):
        buttons = buttons_from_shelf_text(LEGACY_SHELF)
        text = "\n".join(button_mel(b, tool_tag("x")) for b in buttons)
        self.assertEqual(buttons_from_shelf_text(text), buttons)


class PythonButtonsTest(unittest.TestCase):
    def test_button_made_in_code(self):
        [button] = buttons_from_python_text(MODULE_SHELF_PY, images=["buildModifier.png"])
        self.assertEqual(button, ButtonSpec(
            label="Build",
            tooltip="Build: click to apply to the selected meshes, double-click for options",
            icon="buildModifier.png",  # image=_icon() can't be read, but the file names one of the tool's images
            command="import build_modifier.shelf\nbuild_modifier.shelf.on_click()",
            language="python",
            double_click="import build_modifier.shelf\nbuild_modifier.shelf.on_double_click()",
            overlay="Build",
        ))
        self.assertEqual(buttons_from_python_text(MODULE_SHELF_PY)[0].icon, "")

    def test_short_flags_constants_and_defaults(self):
        text = (
            "from maya import cmds as mc\n"
            "PKG = 'tool'\n"
            "mc.shelfButton(l='T', c='import ' + PKG + '; ' + PKG + f'.run()', i='icons/tool.png')\n"
            "mc.shelfButton(l='M', c='toolMel;', i1='mine.png', stp='mel')\n"
            "shelfButton(c=\"print(1)\")\n"
        )
        first, second, third = buttons_from_python_text(text, images=["tool.png"])
        self.assertEqual((first.label, first.command, first.icon, first.language), ("T", "import tool; tool.run()", "tool.png", "mel"))
        self.assertEqual((second.icon, second.language), ("mine.png", "mel"))
        self.assertEqual(third.command, "print(1)")

    def test_skips_what_it_cannot_read(self):
        text = (
            "import os\n"
            "from maya import cmds\n"
            "root = os.path.dirname(__file__)\n"
            "cmds.shelfButton(command='import sys; sys.path.append(%r)' % root)\n"  # built at run time
            "cmds.shelfButton(command=make_command())\n"
            "cmds.shelfButton(command='x()', sourceType=LANG)\n"  # unknown language
            "cmds.shelfButton('b', edit=True, command='edited()')\n"
            "cmds.shelfButton('b', q=1, c=1)\n"
        )
        self.assertEqual(buttons_from_python_text(text), [])
        self.assertEqual(buttons_from_python_text("def broken(:\n"), [])


class FileBackendTest(TempDirTest):
    def test_add_and_remove_keeps_other_buttons(self):
        backend = FileShelfBackend(self.path("shelves"))
        backend.ensure_shelf("EasyTool")
        self.write("shelves/shelf_EasyTool.mel",
                   "global proc shelf_EasyTool () {\n" + USER_BLOCK + "}\n")
        backend.add_buttons("EasyTool", [ButtonSpec(label="A", command="a")], tool_tag("one"))
        backend.add_buttons("EasyTool", [ButtonSpec(label="B", command="b")], tool_tag("two"))
        self.assertEqual(len(backend.button_blocks("EasyTool")), 3)

        self.assertEqual(backend.remove_buttons("EasyTool", tool_tag("one")), 1)
        blocks = backend.button_blocks("EasyTool")
        self.assertEqual(len(blocks), 2)
        self.assertIn("Mine", blocks[0])
        self.assertIn('"easytool:two"', blocks[1])
        self.assertEqual(backend.list_shelves(), ["EasyTool"])

    def test_tag_match_is_exact(self):
        backend = FileShelfBackend(self.path("shelves"))
        backend.add_buttons("S", [ButtonSpec(label="A", command="a")], tool_tag("pivot-snap-pro"))
        self.assertEqual(backend.remove_buttons("S", tool_tag("pivot-snap")), 0)


if __name__ == "__main__":
    unittest.main()
