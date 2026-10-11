"""Drag this file into Maya's viewport to install EasyTool.

It copies the easytool package into your Maya scripts folder, adds an EasyTool button to the
current shelf and opens the panel. On a first install the panel starts with the Jurakii/Tools feed.
"""
import importlib
import inspect
import os
import shutil
import sys


def _here():
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except NameError:  # Maya can run dropped files without __file__
        return os.path.dirname(os.path.abspath(inspect.getsourcefile(_here)))


def onMayaDroppedPythonFile(*_args):  # noqa: N802 - name Maya looks for
    from maya import cmds, mel

    here = _here()
    scripts = os.path.normpath(cmds.internalVar(userScriptDir=True))
    dest = os.path.join(scripts, "easytool")
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    shutil.copytree(os.path.join(here, "easytool"), dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    for name in list(sys.modules):
        if name == "easytool" or name.startswith("easytool."):
            del sys.modules[name]
    importlib.invalidate_caches()
    # Import the copy just installed, not one that happens to sit in Maya's working directory.
    sys.path[:] = [p for p in sys.path if os.path.normcase(os.path.normpath(p or ".")) != os.path.normcase(scripts)]
    sys.path.insert(0, scripts)

    from easytool.core.shelf import MayaShelfBackend

    shelf_top = mel.eval("$easyToolTmp = $gShelfTopLevel")
    shelf = cmds.tabLayout(shelf_top, query=True, selectTab=True)
    for child in cmds.shelfLayout(shelf, query=True, childArray=True) or []:
        full = cmds.shelfLayout(shelf, query=True, fullPathName=True) + "|" + child
        if cmds.objectTypeUI(full) == "shelfButton" and cmds.shelfButton(full, query=True, docTag=True) == "easytool:self":
            cmds.deleteUI(full)
    icon = os.path.join(dest, "resources", "icons", "easytool.png").replace("\\", "/")
    cmds.shelfButton(
        parent=shelf,
        label="EasyTool",
        annotation="Open EasyTool",
        image=icon,
        image1=icon,
        style="iconOnly",
        command="import easytool; easytool.show()",
        sourceType="python",
        docTag="easytool:self",
    )
    MayaShelfBackend(os.path.normpath(cmds.internalVar(userShelfDir=True))).save(shelf)

    import easytool

    easytool.show()
    print(f"EasyTool {easytool.__version__} installed to {dest}. The EasyTool button is on the {shelf} shelf.")
