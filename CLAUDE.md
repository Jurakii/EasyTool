# EasyTool

A panel docked inside Maya that installs, updates and uninstalls shelf tools (buttons, icons and scripts) from feeds, GitHub repos, `.zip` links and folders, and updates itself. Version 0.9.0 (beta); tested on Windows in Maya 2024 (PySide2) and 2025 (PySide6).

## Layout

- `easytool/core/`: all logic, with **no Qt imports**, so it can be tested with plain Python.
  - `sources.py`: feeds, GitHub, zips
  - `installer.py`: copying, conflicts, backups, rollback
  - `shelf.py`: Maya and file shelf backends
  - `selfupdate.py`: EasyTool updating itself
- `easytool/ui/`: the panel (`panel.py`), dialogs, theme, and the Maya dock (`dock.py`).
- `easytool/qt.py`: the PySide2/PySide6 compatibility layer. Import Qt only through it.
- `drag_into_maya.py` is the user-facing installer. `tools/` has the build, preview and icon scripts. `examples/` has two sample tools.
- `docs/AUTHORING.md` covers making tools installable; `docs/DEVELOPMENT.md` covers releasing and the Maya pitfalls. Read the pitfalls before touching ui/, dock or shelf code.

## Commands

```
cd tests && python -m unittest                                         # core tests (Python 3.10+)
"C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe" -m unittest        # run from tests/; also with Maya2024
"C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe" tools\preview_panel.py [--screenshot out.png]
python tools\build_release.py                                          # dist\EasyTool-<version>.zip
```

## Rules

- **Maya-specific crashes** (details in docs/DEVELOPMENT.md):
  - never call `widget.style()`; use `widgets.set_prop`
  - worker threads must not touch Qt; use `ui/workers.run_async`
  - edit shelves through `MayaShelfBackend`, never the `.mel` files while Maya runs
  - create the dock already docked
- **UI:** stays in the Warm Graphite theme (`ui/theme.py` tokens, Archivo and IBM Plex Mono). Use the `bold` keyword or the "Archivo SemiBold" family, never numeric font weights; Qt 5 reads them on a different scale.
- **Install records** are per Maya version (`installed-<version>.json`). Tools are tracked by id, and shelf buttons carry `docTag "easytool:<id>"`.
- **Testing inside Maya:** use a throwaway `MAYA_APP_DIR` so the user's prefs are never touched. Ask before launching Maya; it opens windows on the user's desktop.

## Distribution

- **The feed:** `tools.json` in https://github.com/Jurakii/Tools is both the default feed and EasyTool's update source. EasyTool reads its `projects` format; enabled projects with a `.zip` link become tools.
- **Self-update:** EasyTool updates itself only from the entry with id `easytool` in that feed. That entry's version must match `__version__` in the release zip.
- **Releases:** GitHub releases on https://github.com/Jurakii/EasyTool (tag `v<version>`, asset `EasyTool-<version>.zip`). Steps are in docs/DEVELOPMENT.md.
- **The user's own tools:** don't edit the tools in Jurakii/Tools; suggest fixes instead. Pushing, tagging, releasing and editing `tools.json` are public actions: ask first.
