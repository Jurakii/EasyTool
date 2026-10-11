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
