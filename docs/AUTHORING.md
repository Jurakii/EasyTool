# Making your tools installable

EasyTool installs a tool from a folder or `.zip` that holds shelf buttons, icons and scripts, or a Maya module. Users get tools from sources, which can be a GitHub repo, a `.zip` link, a feed that lists many tools, or a local or network folder.

## The simplest case: zips you already have

Classic "drag these into your prefs folder" zips work as they are, with no extra files:

```
MyTool.zip
  MyTool.mel                 loose .mel/.py files: copied to Maya's scripts folder
  shelves/shelf_MyTool.mel   its buttons go on the shelf the user picked
  icons/MyTool.png           copied to Maya's icons folder
```

- **Buttons:** the buttons in `shelf_*.mel` go on the user's chosen shelf, with their labels, icons and commands kept. Set `"ownShelf": true` (in the feed entry or an `easytool.json`) to install the file as its own shelf tab instead.
- **Scripts:** a `scripts/` folder works as well as loose files at the top of the zip. `userSetup` files and installer scripts (`install*`, `drag*`) are never copied.
- **Icons:** ship `name.png` plus `name_150.png` and `name_200.png`, so icons stay sharp on scaled displays.

## Other layouts that work as they are

EasyTool also recognizes these, with no extra files:

| Layout | What EasyTool does |
| --- | --- |
| **Maya module:** a `.mod` file at the top, next to `scripts/`, `plug-ins/` and `icons/` | Copies the whole folder to `maya/<version>/modules/` and writes the `.mod` file next to it, pointing at the copy. The tool works in the open Maya session straight away; from the next start, Maya loads it as a module. |
| **Plug-ins without a `.mod` file:** a `plug-ins/` folder | Installed as a module too, with a `.mod` file EasyTool writes. This keeps the tool's folders together, so code that finds its plug-ins or icons relative to itself keeps working. |
| **A Python package at the top:** `my_tool/__init__.py` | Copied to the scripts folder as a package. Folders named `test*` are left out. |
| **Maya's own layout:** `scripts/`, `prefs/icons/`, `prefs/shelves/` | Treated like `scripts/`, `icons/` and `shelves/`. |
| **Wrapper folders:** `MyTool-1.0/MyTool/…` | EasyTool steps into a few nested top folders, but never into `scripts/`, `icons/` and the like, or into a Python package. |

**Buttons made in code.** Many tools add their shelf button from Python, in an installer or a `shelf.py`, instead of shipping a shelf file. When a tool has no shelf file, EasyTool reads (never runs) its Python files for `cmds.shelfButton(...)` calls and makes the same buttons.
- It reads flags that are plain strings, or names set to plain strings at the top of the file, so `command=CLICK_COMMAND` works. A button whose command is built at run time is skipped.
- When the image comes from a function (`image=_icon()`), the button gets the tool's icon that the file names, or the tool's only icon.
- Files in `tests/`, `docs/` and `examples/` folders are left out.

**Modules in more detail:**
- **Paths inside the `.mod` file** keep their place. A module whose path is `.` points at the copy, and `./platforms/2024` points at the same folder inside it. A path from the author's own machine (`C:/dev/MyTool`) points at the tool's folder of that name, if it has one.
- **Version:** the module's version is the tool's version when nothing else gives one.
- **Buttons** point at the module's own icons by full path, because Maya only finds a module's icons by name after a restart.
- **Updating a module whose compiled plug-in is loaded** stops with a message to unload the plug-in or restart Maya, because Windows can't move files that are in use. Uninstalling one keeps its record until the files can be deleted.

## easytool.json (optional)

For more control, put an `easytool.json` at the top of the tool's folder or zip:

```json
{
  "name": "Pivot Snap",
  "id": "pivot-snap",
  "version": "1.0.0",
  "category": "Modeling",
  "description": "Move pivots to the center, the bottom center or the world origin.",
  "icons": "icons",
  "scripts": "scripts",
  "buttons": [
    {
      "label": "PIV",
      "tooltip": "Pivot Snap: center",
      "icon": "pivotSnap.png",
      "language": "python",
      "command": "import pivot_snap; pivot_snap.to_center()"
    }
  ]
}
```

| Key | Meaning |
| --- | --- |
| `name`, `id` | Display name and a stable id. The id defaults to the name, slugified. |
| `version` | Compared numerically to offer updates. For GitHub repos, the release tag is used if this is missing. |
| `category` | Modeling, Rigging, Animation, Lighting, Rendering, FX, Pipeline or Utility. Sets the tile color. |
| `icons` | Folder whose images are copied to Maya's icons folder. |
| `scripts` | Folder whose contents (Python packages, `.py`, `.mel`) are copied to Maya's scripts folder. |
| `buttons` | Shelf buttons. `language` is `python` or `mel`. Also `doubleClick` (a second command) and `overlay` (text drawn over the icon). A button without an icon gets Maya's default icon with its label on top. |
| `shelf` | Path, or list of paths, to `shelf_*.mel` files whose buttons are added too. |
| `ownShelf` | `true` installs those shelf files as their own tabs instead. |

A tool with an `easytool.json` and a `.mod` file (or a `plug-ins/` folder) still installs as a module. Its buttons come only from `buttons` and `shelf`, never from its code.

See `examples/` for a Python tool and a MEL tool.

## Feeds: one link for all your tools

A feed lists your tools. Users add its link once, and EasyTool checks it whenever the panel opens or they press refresh.

```json
{
  "tools": [
    {
      "name": "Assign RGB",
      "id": "assign-rgb",
      "version": "1.0.0",
      "category": "Rendering",
      "description": "Make R, G, B (and C, M, Y) shaders and assign them from a small window.",
      "url": "tools/AssignRGB.zip",
      "icon": "icons/AssignRGB.png"
    },
    {
      "name": "Private Tool",
      "version": "2.0.0",
      "url": "https://yoursite.com/downloads/PrivateTool-2.0.0.zip"
    }
  ]
}
```

- **`url`:** relative to the feed (a zip in the same repo or folder), a full link to anywhere, or a local or network path.
- **`version`:** what users get updates from. Upload the new zip, bump the version, and users see **Update**. With a version, the list loads from the feed alone. Without one, EasyTool downloads the zip on every refresh to look inside.
- **`icon`** (optional): shown in the list before the tool is installed.
- **Other entry types:** `{"repo": "owner/name"}` is a GitHub repo, using its latest release. `{"path": "subfolder"}` is a tool folder next to the feed.

**Already have a `tools.json` for a portfolio site?** If it has a `projects` list, EasyTool reads it as a feed. Each enabled project whose download link ends in `.zip` becomes a tool. Everything else is left out.

| `tools.json` field | Becomes in EasyTool |
| --- | --- |
| `id` | id |
| `title` | name |
| `version` | version |
| `desc` | description |
| first file in `media.files` | icon |
| `tags` | category, when a tag matches one (`Shaders` counts as Rendering) |

**In a GitHub repo:** put the feed at the repo root as `index.json` (or `tools.json`), and users add the repo link (`https://github.com/you/repo`).
- EasyTool reads the feed from the default branch, so edits show up after a push, without making a release. GitHub's raw file cache can delay that by about 5 minutes.
- Users can also add a file-page link (`…/blob/main/index.json`), or link to a feed with any other file name.

**Public and private tools:** anything in a feed can be downloaded by anyone who has the feed's link. Keep tools you don't want public in a second feed, shared only with the people who should have it (a private link, or a folder on a network share). EasyTool merges all of a user's sources into one list.

**GitHub limits:** GitHub allows 60 anonymous API requests an hour.
- Feeds and zip links don't use the API. Only `repo` entries without a version do, so prefer `url` entries.
- Setting the `EASYTOOL_GITHUB_TOKEN` environment variable raises the limit.
