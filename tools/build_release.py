"""Build the EasyTool release zip: drag_into_maya.py, the easytool/ package, docs/, README, CHANGELOG and LICENSE.

    python tools/build_release.py                      # dist/EasyTool-<version>.zip
    python tools/build_release.py --version 9.9.9      # stamp another version into the zipped copy (testing updates)

Attach the zip to a GitHub release, then list it in the feed with the id "easytool" and its
version, so installed copies offer the update.
"""
import argparse
import os
import re
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION = re.compile(r"""^__version__\s*=\s*["']([^"']+)["']""", re.MULTILINE)
SKIP_DIRS = {"__pycache__"}
SKIP_EXTS = (".pyc",)


def tree_files(folder):
    for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, folder)):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            if not name.endswith(SKIP_EXTS):
                full = os.path.join(dirpath, name)
                yield full, os.path.relpath(full, ROOT).replace(os.sep, "/")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", help="version to stamp into the zipped easytool/__init__.py")
    parser.add_argument("--out", default=os.path.join(ROOT, "dist"))
    args = parser.parse_args()

    init_path = os.path.join(ROOT, "easytool", "__init__.py")
    with open(init_path, encoding="utf-8") as fh:
        init_text = fh.read()
    version = args.version or VERSION.search(init_text).group(1)

    os.makedirs(args.out, exist_ok=True)
    zip_path = os.path.join(args.out, f"EasyTool-{version}.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in ("drag_into_maya.py", "README.md", "CHANGELOG.md", "LICENSE"):
            if os.path.isfile(os.path.join(ROOT, name)):
                zf.write(os.path.join(ROOT, name), name)
        for full, rel in list(tree_files("easytool")) + list(tree_files("docs")):
            if rel == "easytool/__init__.py" and args.version:
                zf.writestr(rel, VERSION.sub(f'__version__ = "{version}"', init_text, count=1))
            else:
                zf.write(full, rel)
    print(zip_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
