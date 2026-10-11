# EasyTool

EasyTool is a panel that docks inside Maya and installs shelf tools for you. Pick tools from a list, press **Install**, and their buttons appear on your shelf, with their icons and scripts copied to the right places. EasyTool tells you when updates are out, and uninstalls cleanly: it only removes files it put there itself.

- Works with Maya 2022 and later on Windows. Tested in Maya 2024 and 2025.
- Starts with the tools from [Jurakii/Tools](https://github.com/Jurakii/Tools). You can add more sources.

## Install

1. Download the latest `EasyTool-<version>.zip` from the releases page and unzip it anywhere.
2. Drag `drag_into_maya.py` from the unzipped folder into the Maya viewport.

EasyTool copies itself into your Maya scripts folder, puts an **EasyTool** button on the shelf you have open, and opens the panel next to the Channel Box. After that, open it with the shelf button, or from the Script Editor (Python tab) with:

```python
import easytool; easytool.show()
```

**More than one Maya version?** Drag the file into each one. Every version keeps its own folders and its own list of installed tools.

## Using the panel

- **Installing tools:** tick tools and press **Install**, or press **Add** on a single row. Right-click a row to reinstall or uninstall a tool, or open its homepage.
- **Updates:** tools with a newer version show **Update**, and the **Updates** filter lists them all.
- **Shelf:** choose which shelf new buttons go on. The default is a new `EasyTool` shelf. Pick an existing one, or choose *New shelf…*.
- **Folders:** where shelves, icons and scripts are installed, filled in from Maya. Use the folder buttons to choose somewhere else (for example, a studio share). *⋯ → Use Maya's default folders* undoes that.
- **Sources:** *⋯ → Manage sources…* adds or removes places to get tools from: a GitHub repo, a `.zip` link, a feed (`index.json`), or a local or network folder.
- **When a file already exists,** EasyTool asks before touching it:
  - **Replace:** your file is backed up, and put back if you uninstall the tool.
  - **Keep both:** icons only. The new icons are saved under a new name.
  - **Skip:** your file stays as it is.

**Only add sources you trust.** Shelf buttons run their tool's code when you click them, just like a tool you install by hand.

## Updating EasyTool

When a new version of EasyTool is out, a bar at the top of the panel says so. Press **Update**, then **Reopen**. There's no need to restart Maya.

## Where things go

- **Tools:** each tool's files go in Maya's own folders for that version (`Documents/maya/<version>/prefs/shelves`, `prefs/icons` and `scripts`). Tools that are Maya modules (they come with a `.mod` file, or with plug-ins) go in `Documents/maya/<version>/modules`, as one folder each. *⋯ → Open modules folder* shows them.
- **EasyTool's own data:** its settings, download cache, backups and installed-tool lists (one per Maya version) live in `Documents/maya/easytool/`.

## Removing EasyTool

1. Uninstall any tools you don't want to keep (right-click → **Uninstall**).
2. Delete the `easytool` folder from `Documents/maya/<version>/scripts`.
3. Remove the EasyTool shelf button: right-click it and choose **Delete**.
4. Optionally, delete `Documents/maya/easytool`.

## For tool authors and developers

- [Making your tools installable](docs/AUTHORING.md): zips, `easytool.json`, and feeds.
- [Developing and releasing EasyTool](docs/DEVELOPMENT.md).

## License

EasyTool is released under the MIT License (see `LICENSE`). The bundled fonts, Archivo and IBM Plex Mono, are under the SIL Open Font License (see `easytool/resources/fonts`).
