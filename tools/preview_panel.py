"""Open the EasyTool panel outside Maya, against a throwaway Maya folder, for UI work.

    mayapy tools/preview_panel.py                          # a normal window
    mayapy tools/preview_panel.py --screenshot panel.png   # render to a PNG and exit
        [--demo]                 pre-install Scene Cleaner so the list shows an installed tool
        [--select pivot-snap]    tick a tool so the footer shows a selection
"""
import argparse
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--screenshot")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--select", action="append", default=[])
    parser.add_argument("--size", default="400x860")
    args = parser.parse_args()

    from easytool.core.context import AppContext
    from easytool.core.paths import MayaFolders
    from easytool.core.sources import make_source
    from easytool.qt import QtCore, QtWidgets, exec_
    from easytool.ui.panel import EasyToolPanel

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    tmp = tempfile.mkdtemp(prefix="easytool-preview-")
    try:
        base = os.path.join(tmp, "2024")
        folders = MayaFolders(
            os.path.join(base, "prefs", "shelves"),
            os.path.join(base, "prefs", "icons"),
            os.path.join(base, "scripts"),
            "2024",
        )
        for kind in ("shelves", "icons", "scripts"):
            os.makedirs(folders.get(kind))
        ctx = AppContext(app_dir=tmp, folders=folders, default_sources=())
        ctx.settings.add_source(make_source(os.path.join(ROOT, "examples")))
        if args.demo:
            [cleaner] = [t for t in ctx.resolver.list_tools(ctx.settings.sources[0]) if t.id == "scene-cleaner"]
            ctx.installer().install(cleaner, ctx.resolver.fetch_payload(cleaner))

        panel = EasyToolPanel(ctx, sync=True)
        panel.setWindowTitle("EasyTool (preview)")
        width, height = (int(n) for n in args.size.split("x"))
        panel.resize(width, height)
        if args.select:
            panel.selected.update(args.select)
            panel._render()
        if args.screenshot:  # lay out and paint for real, without putting a window on screen
            panel.setAttribute(QtCore.Qt.WA_DontShowOnScreen, True)
        panel.show()
        if args.screenshot:
            for _ in range(5):
                app.processEvents()
            panel.grab().save(args.screenshot)
            print("saved", args.screenshot)
        else:
            exec_(app)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
