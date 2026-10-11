# Developing and releasing EasyTool

## Layout

```
drag_into_maya.py   the installer users drag into Maya
easytool/core/      logic with no Qt: manifests, sources and feeds, downloads, installer, shelves, Maya modules, self-update
easytool/ui/        the panel (Warm Graphite theme), dialogs and the Maya dock
easytool/resources/ icons, stylesheet images and the bundled fonts
examples/           two sample tools (Python and MEL) and an index.json
tests/              unit tests for easytool/core
tools/              preview_panel.py, build_release.py, make_icons.py
docs/               this guide and the authoring guide
```

## Running things

Run the tests with any Python 3.10 or later, including Maya's `mayapy`:

```
cd tests
python -m unittest
```

Open the panel outside Maya, against a throwaway Maya folder and the bundled examples:

```
"C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe" tools\preview_panel.py
```

Add `--screenshot out.png` to render the panel to a file instead of opening a window.

`tools/make_icons.py` re-renders the PNG icons for EasyTool and the examples.

## Releasing a new version

EasyTool updates itself from one feed, the update source: `https://github.com/Jurakii/Tools` by default.
- It checks that feed even if a user removed it from their sources.
- Only that feed can offer an EasyTool update, because installing one replaces EasyTool's own code.
- EasyTool never lists itself as a tool.

1. Bump `__version__` in `easytool/__init__.py`, and add the changes to `CHANGELOG.md`.
2. Run `python tools/build_release.py`. It builds `dist/EasyTool-<version>.zip`, which holds `drag_into_maya.py`, `easytool/`, `docs/`, the README and the LICENSE.
3. Create a GitHub release for the tag `v<version>` and attach the zip.
4. In the update source's feed, list EasyTool with the id `easytool`, the new version, and the zip's link. In `tools.json`, that's a project:

   ```json
   {
     "id": "easytool",
     "title": "EasyTool",
     "version": "0.9.0",
     "desc": "Install Maya shelf tools from GitHub and anywhere else",
     "enabled": true,
     "links": [{ "label": "Download", "url": "https://github.com/Jurakii/EasyTool/releases/download/v0.9.0/EasyTool-0.9.0.zip" }]
   }
   ```

Installed copies offer the update the next time their panel opens. A copy that runs from a source checkout (next to `drag_into_maya.py`, or in a git repo) is never overwritten; its panel says to update from the repo instead.

## Things learned the hard way in Maya

These were all found by running EasyTool inside Maya 2024 and 2025. Keep them in mind when changing the UI or the shelf code.

- **Never call `widget.style()`, for example `style().unpolish(widget)`.** PySide2 inside Maya hands Python Maya's application style and later frees it, which corrupts memory and crashes Maya. `widgets.set_prop` restyles by re-applying the widget's own stylesheet instead.
- **Worker threads must not touch Qt.** `ui/workers.py` passes results back through a plain queue that a main-thread timer reads.
- **Create the dock already docked.** `dock.show()` creates the `workspaceControl` already tabbed, and the panel as a Qt child of Maya's widget, so Maya owns it. Creating it floating and then moving it makes Maya delete the widget while Python still holds it.
  - Use `loadImmediately=True` (a new tab starts behind the Channel Box), and `r=True` to raise it.
- **Maya rewrites every loaded shelf file when it quits.** So shelves are edited live with `maya.cmds` and saved with `saveShelf`, never by editing the `.mel` file behind Maya's back.
- **Maya builds a shelf's buttons only when its tab is first opened.** `MayaShelfBackend` calls `loadShelf <index>` before reading, editing or saving a shelf; otherwise saving an unopened shelf would write it out empty.
- **Qt 5 (Maya 2024) reads stylesheet `font-weight` numbers on its own scale,** where 600 is Bold and 700 is Black. The theme uses the `bold` keyword, and names the "Archivo SemiBold" family directly, instead of numbers.
- **A Maya started from a hidden console stays hidden.** The in-Maya tests show its main window themselves.
- **Maya reads `.mod` files only when it starts.** `MayaShelfBackend.load_module` adds a new module's folders to the running session itself, using MEL's `putenv` and then `rehash`. Maya's own `getenv` doesn't see changes made through `os.environ`; `loadPlugin` happens to, MEL's script path doesn't.
- **Modules, as checked in Maya 2024:**
  - `maya/<version>/modules` comes before the shared `maya/modules` on `MAYA_MODULE_PATH`.
  - When two `.mod` files name the same module, Maya loads only the first one it finds, so a module EasyTool installs wins over a hand-installed copy with the same name.
  - A relative module path (`./name`) is relative to the `.mod` file.
