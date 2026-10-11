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
