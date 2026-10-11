# Making your tools installable

EasyTool installs a tool from a folder or `.zip` that holds shelf buttons, icons and scripts. Users get tools from sources, which can be a GitHub repo, a `.zip` link, a feed that lists many tools, or a local or network folder.

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
