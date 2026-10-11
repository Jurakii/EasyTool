import unittest

from helpers import LEGACY_SHELF, TempDirTest

from easytool.core.models import ButtonSpec
from easytool.core.shelf import FileShelfBackend, button_mel, buttons_from_shelf_text, mel_string, tool_tag

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
