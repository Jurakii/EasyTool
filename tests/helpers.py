import io
import os
import shutil
import sys
import tempfile
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLES = os.path.join(ROOT, "examples")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from easytool.core.net import NotFound  # noqa: E402


class TempDirTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="easytool-test-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def path(self, *parts):
        return os.path.join(self.tmp, *parts)

    def read(self, path):
        with open(path, "rb") as fh:
            return fh.read()

    def write(self, rel, data=b"x"):
        path = self.path(*rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(data if isinstance(data, bytes) else data.encode("utf-8"))
        return path


class FakeHttp:
    """Stands in for easytool.core.net.Http. Unknown URLs raise NotFound."""

    def __init__(self, json_map=None, files=None):
        self.json_map = json_map or {}
        self.files = files or {}
        self.calls = []

    def fetch_json(self, url):
        self.calls.append(url)
        if url in self.json_map:
            return self.json_map[url]
        raise NotFound(url)

    def fetch_bytes(self, url):
        self.calls.append(url)
        if url in self.files:
            return self.files[url]
        raise NotFound(url)

    def download(self, url, dest):
        self.calls.append(url)
        if url not in self.files:
            raise NotFound(url)
        with open(dest, "wb") as fh:
            fh.write(self.files[url])


def zip_folder(folder, top="owner-repo-abc123"):
    """Zip a folder. With top, everything sits under one directory, like GitHub's zipball."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for dirpath, _dirs, files in os.walk(folder):
            for name in files:
                full = os.path.join(dirpath, name)
                rel = os.path.relpath(full, folder).replace(os.sep, "/")
                zf.write(full, f"{top}/{rel}" if top else rel)
    return buf.getvalue()


# A shelf file as Maya saves it: commands on one line with \n, \t and \" escapes.
LEGACY_SHELF = r'''global proc shelf_ColorTools () {
    global string $gBuffStr;
    global string $gBuffStr0;
    global string $gBuffStr1;


    shelfButton
        -enableCommandRepeat 1
        -flexibleWidthType 3
        -annotation "Assign RGB Standard Surface"
        -label "Assign RGB"
        -labelOffset 0
        -overlayLabelColor 0.8 0.8 0.8
        -image "AssignRGB.png"
        -image1 "AssignRGB.png"
        -style "iconOnly"
        -command "// Assign RGB\nif (!`objExists \"R\"`) {\n\tshadingNode -asShader standardSurface -name \"R\";\n}"
        -sourceType "mel"
        -commandRepeatable 1
    ;
    shelfButton
        -annotation "Second"
        -label "Second"
        -imageOverlayLabel "2nd"
        -image "Second.png"
        -command "print(\"hi\")"
        -sourceType "python"
    ;

}
'''


def make_legacy_tool(folder):
    """A "drag these into your prefs" zip: loose scripts, shelves/ and icons/, no easytool.json."""
    files = {
        "AssignRGB.mel": "// Assign RGB\n",
        "AssignRGBCMY.mel": "// Assign RGBCMY\n",
        "userSetup.py": "# must never be copied over the user's own\n",
        "install.mel": "// an installer, not part of the tool\n",
        "shelves/shelf_ColorTools.mel": LEGACY_SHELF,
        "icons/AssignRGB.png": "png",
        "icons/Second.png": "png",
    }
    for rel, text in files.items():
        path = os.path.join(folder, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
    return folder


# Trimmed from a real module (Build modifier): its button is made in code, not in a shelf file.
MODULE_SHELF_PY = r'''"""Shelf button for Build."""
import os

from maya import cmds, mel

LABEL = "Build"
ICON = "buildModifier.png"
CLICK_COMMAND = "import build_modifier.shelf\nbuild_modifier.shelf.on_click()"
DOUBLE_CLICK_COMMAND = "import build_modifier.shelf\nbuild_modifier.shelf.on_double_click()"


def install(shelf=None):
    for button in cmds.shelfLayout(shelf, query=True, childArray=True) or []:
        if "build_modifier" in (cmds.shelfButton(button, query=True, command=True) or ""):
            return button
    return cmds.shelfButton(
        parent=shelf,
        label=LABEL,
        imageOverlayLabel=LABEL,
        image=_icon(),
        annotation="Build: click to apply to the selected meshes, double-click for options",
        sourceType="python",
        command=CLICK_COMMAND,
        doubleClickCommand=DOUBLE_CLICK_COMMAND,
    )


def _icon():
    path = os.path.join(os.path.dirname(__file__), "..", "..", "icons", ICON)
    return path if os.path.exists(path) else "pythonFamily.png"
'''


def make_module_tool(folder):
    """A Maya module: a .mod file whose path is ".", with scripts/, plug-ins/ and icons/ beside it."""
    files = {
        "build_modifier.mod": "+ build_modifier 1.0 .\n",
        "install_drop.py": "def onMayaDroppedPythonFile(*_):\n    import build_modifier.shelf\n",
        "README.md": "# Build\n",
        ".gitattributes": "* text=auto\n",
        "icons/buildModifier.png": "png",
        "plug-ins/buildModifierNode.py": "# the node\n",
        "scripts/build_modifier/__init__.py": "",
        "scripts/build_modifier/shelf.py": MODULE_SHELF_PY,
        "tests/test_in_maya.py": 'cmds.shelfButton(command="print(1)", sourceType="python")\n',
    }
    for rel, text in files.items():
        path = os.path.join(folder, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
    return folder
