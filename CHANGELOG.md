# Changelog

## 0.9.0 (beta)

The first release.

- **The panel:** docks next to the Channel Box, in the Warm Graphite style, and works in Maya 2022–2024 (PySide2) and 2025 and later (PySide6). Tested in Maya 2024 and 2025.
- **Sources:**
  - GitHub repos, `.zip` links, feeds (`index.json`, or a portfolio site's `tools.json`), and local or network folders.
  - Starts with the Jurakii/Tools feed.
- **Installing:**
  - Shelf buttons, icons and scripts go into Maya's folders, and buttons from `shelf_*.mel` files go on the shelf you choose.
  - "Drag into your prefs" zips install as they are.
  - When a file already exists, it asks whether to replace it (with a backup), keep both, or skip it. A cancelled install puts everything back.
- **Updates and uninstalling:**
  - Tools: updates come from the version numbers in the feed, and uninstalling removes only what EasyTool installed, putting back any files it replaced.
  - EasyTool itself: updates come from its update source and take effect without restarting Maya.
- **One list per Maya version:** each Maya version keeps its own folders and its own list of installed tools.

## 0.9.1 (beta)

Install icon change

- Testing auto update system

## 0.9.2 (beta)

More ways to package a tool. Tools shared as Maya modules, Python packages or Maya's own folder layout now install as they are, with no `easytool.json`.

- **Maya modules:** a tool with a `.mod` file installs as one folder in `Documents/maya/<version>/modules`, with its `.mod` file pointing at it.
  - It works in the open Maya session straight away: its scripts, plug-ins and icons are added to Maya's paths, so there's no need to restart.
  - Paths in the `.mod` file are kept, including per-version and per-platform sections.
  - A tool with a `plug-ins/` folder but no `.mod` file installs as a module too.
- **Buttons made in code:** a tool with no shelf file gets the buttons its Python code makes with `cmds.shelfButton`, read from the code without running it.
- **More layouts:**
  - Python packages at the top of a zip are copied to the scripts folder whole.
  - Maya's own `prefs/icons` and `prefs/shelves` folders are recognized.
  - Zips wrapped in several nested folders are unwrapped.
  - A folder source can hold several modules, each listed as its own tool.
- **Files in use:**
  - When an update has to replace a file that is in use (often a loaded plug-in), it now stops cleanly and asks you to unload it or restart Maya, instead of leaving a half-replaced folder.
  - Uninstalling such a tool keeps its record, so removing it again finishes the job.
- **Panel:** *⋯ → Open modules folder*.
