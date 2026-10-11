"""Turn sources (GitHub repos, feeds, .zip links, folders) into installable tools.

A feed is an index.json listing tools. Entries can point at GitHub repos, .zip files anywhere
(relative to the feed, absolute URLs, or local/network paths) or subfolders. Entries that give a
"version" are listed straight from the feed, so the list loads without downloading anything and a
version bump is what tells users an update is available.
"""
from __future__ import annotations

import hashlib
import json
import os
import posixpath
import re
import shutil
import zipfile
from dataclasses import asdict, dataclass, field
from urllib.parse import urljoin, urlparse

from .manifest import (
    IMAGE_EXTS, INDEX_NAME, MANIFEST_NAME, ManifestError, load_manifest, normalize_category, parse_manifest, read_tool, scan_folder,
)
from .models import CATEGORIES, Location, ToolInfo, slugify
from .net import Http, NetError, NotFound

KIND_LABELS = {"github": "GitHub repo", "index": "Feed (index.json)", "zip": ".zip download", "folder": "Folder"}
FEED_NAMES = (INDEX_NAME, "tools.json")  # looked for at the root of a repo or folder
TAG_CATEGORIES = {"shaders": "Rendering", "shading": "Rendering", "materials": "Rendering", "lookdev": "Rendering"}

GITHUB_URL = re.compile(
    r"^(?:https?://)?(?:www\.)?github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?"
    r"(?:/(?:tree|releases/tag)/([^/?#]+))?/?(?:[?#].*)?$",
    re.IGNORECASE,
)
GITHUB_SHORT = re.compile(r"^([\w.-]+)/([\w.-]+?)(?:@(\S+))?$")
GITHUB_FILE = re.compile(r"^(?:https?://)?(?:www\.)?github\.com/([\w.-]+)/([\w.-]+)/(?:blob|raw)/([^?#]+)", re.IGNORECASE)


@dataclass
class Source:
    url: str
    kind: str
    name: str = ""
    enabled: bool = True

    @property
    def id(self) -> str:
        return hashlib.sha1(self.url.strip().lower().encode("utf-8")).hexdigest()[:10]

    @property
    def kind_label(self) -> str:
        return KIND_LABELS.get(self.kind, self.kind)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SourceResult:
    source: Source
    tools: list = field(default_factory=list)
    errors: list = field(default_factory=list)


def is_remote(text: str) -> bool:
    return bool(re.match(r"^[a-z][a-z0-9+.-]*://", text, re.IGNORECASE))


def _looks_like_path(text: str) -> bool:
    return bool(re.match(r"^[a-zA-Z]:[\\/]", text)) or text.startswith(("\\\\", "/", "~")) or os.path.isdir(text)


def normalize_url(text: str) -> str:
    """Turn a GitHub file page link (…/blob/main/feed.json) into the raw file it shows."""
    text = text.strip().strip('"')
    match = GITHUB_FILE.match(text)
    if match:
        return f"https://raw.githubusercontent.com/{match.group(1)}/{match.group(2)}/{match.group(3)}"
    return text


def detect_kind(text: str) -> str:
    text = normalize_url(text)
    if not text:
        raise ValueError("Paste a link or choose a folder.")
    local = _looks_like_path(text)
    path = (text if local else urlparse(text if "://" in text else "https://" + text).path).lower()
    if path.endswith(".zip"):
        return "zip"
    if path.endswith(".json"):
        return "index"
    if local:
        return "folder"
    if GITHUB_URL.match(text) or GITHUB_SHORT.match(text):
        return "github"
    if text.lower().startswith(("http://", "https://")):
        raise ValueError("Links need to point at a GitHub repo, a .zip file or an index.json feed.")
    raise ValueError("That doesn't look like a link or a folder.")


def parse_github(text: str):
    """Return (owner, repo, ref) from a GitHub URL or "owner/repo[@ref]" shorthand."""
    text = text.strip()
    match = GITHUB_URL.match(text) or GITHUB_SHORT.match(text)
    if not match:
        raise ValueError(f"Not a GitHub repo: {text}")
    return match.group(1), match.group(2), match.group(3) or ""


def _base_name(location: str) -> str:
    path = urlparse(location).path if is_remote(location) else location
    return os.path.splitext(posixpath.basename(path.replace("\\", "/")))[0]


def default_name(text: str, kind: str) -> str:
    if kind == "github":
        return parse_github(text)[1]
    if kind == "folder":
        return os.path.basename(os.path.normpath(os.path.expanduser(text))) or text
    if kind == "index":
        path = urlparse(text).path if is_remote(text) else text.replace("\\", "/")
        parent = posixpath.basename(posixpath.dirname(path))
        if is_remote(text) and "raw.githubusercontent.com" in text:
            return path.strip("/").split("/")[1]  # the repo name
        return parent or urlparse(text).netloc or text
    return _base_name(text) or urlparse(text).netloc


def make_source(text: str) -> Source:
    url = normalize_url(text)
    kind = detect_kind(url)
    return Source(url=url, kind=kind, name=default_name(url, kind))


def safe_extract(archive: str, dest: str) -> None:
    """Extract a zip, refusing entries that would land outside dest."""
    root = os.path.realpath(dest)
    with zipfile.ZipFile(archive) as zf:
        for member in zf.infolist():
            target = os.path.realpath(os.path.join(dest, member.filename))
            if target != root and not target.startswith(root + os.sep):
                raise ValueError(f"Unsafe path in archive: {member.filename}")
        zf.extractall(dest)


def single_child(folder: str) -> str:
    """Archives often wrap everything in one top folder; step into it."""
    entries = [e for e in os.listdir(folder) if not e.startswith(".") and e != "__MACOSX"]
    if len(entries) == 1 and os.path.isdir(os.path.join(folder, entries[0])):
        return os.path.join(folder, entries[0])
    return folder


def _key(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def is_feed(data) -> bool:
    return isinstance(data, dict) and (isinstance(data.get("tools"), list) or isinstance(data.get("projects"), list))


def category_from_tags(tags) -> str:
    for tag in tags if isinstance(tags, list) else []:
        text = str(tag).strip()
        if normalize_category(text) in CATEGORIES:
            return normalize_category(text)
        if text.lower() in TAG_CATEGORIES:
            return TAG_CATEGORIES[text.lower()]
    return "Utility"


def feed_entries(data) -> list:
    """The tool entries of a feed.

    Besides EasyTool's own {"tools": [...]}, this reads the {"projects": [...]} tools.json that a
    portfolio site uses: enabled projects whose download link is a .zip become installable tools.
    """
    if isinstance(data, dict) and isinstance(data.get("tools"), list):
        return data["tools"]
    if not (isinstance(data, dict) and isinstance(data.get("projects"), list)):
        raise ManifestError('A feed needs a "tools" list')
    entries = []
    for project in data["projects"]:
        if not isinstance(project, dict) or project.get("enabled") is False:
            continue
        links = [link for link in project.get("links") or [] if isinstance(link, dict)]
        url = next((str(link.get("url")) for link in links
                    if str(link.get("url") or "").lower().split("?")[0].endswith(".zip")), "")
        if not url:
            continue
        media = project.get("media") if isinstance(project.get("media"), dict) else {}
        icons = [f for f in media.get("files") or [] if str(f).lower().endswith(IMAGE_EXTS)]
        entries.append({
            "id": project.get("id"),
            "name": project.get("title"),
            "version": project.get("version") or "",
            "description": project.get("desc") or "",
            "category": category_from_tags(project.get("tags")),
            "url": url,
            "icon": icons[0] if icons else "",
        })
    return entries


def _read_json_file(path: str):
    try:
        with open(path, encoding="utf-8-sig") as fh:
            return json.load(fh)
    except ValueError as exc:
        raise ManifestError(f"{path} is not valid JSON: {exc}") from exc
    except OSError as exc:
        raise ValueError(f"Couldn't read {path}: {exc.strerror or exc}") from exc


class Resolver:
    def __init__(self, cache_dir: str, http: Http = None):
        self.cache_dir = cache_dir
        self.http = http or Http()

    # Listing -------------------------------------------------------------

    def list_all(self, sources) -> list:
        results = []
        for source in sources:
            if not source.enabled:
                continue
            result = SourceResult(source)
            try:
                result.tools = self.list_tools(source, result.errors)
            except (NetError, ManifestError, ValueError, OSError, zipfile.BadZipFile) as exc:
                result.errors.append(str(exc))
            for tool in result.tools:
                tool.source_id = source.id
            results.append(result)
        return results

    def list_tools(self, source: Source, errors: list = None) -> list:
        errors = [] if errors is None else errors
        url = normalize_url(source.url)
        if source.kind == "folder":
            return self._folder_tools(os.path.expanduser(url), errors)
        if source.kind == "github":
            owner, repo, ref = parse_github(url)
            return self._github_tools(owner, repo, ref, "", errors)
        if source.kind == "zip":
            return [self._zip_tool(url)]
        if source.kind == "index":
            if is_remote(url):
                return self._index_tools(self.http.fetch_json(url), errors, base_url=url)
            path = os.path.expanduser(url)
            return self._index_tools(_read_json_file(path), errors, base_dir=os.path.dirname(path))
        raise ValueError(f"Unknown source type: {source.kind}")

    def _folder_tools(self, folder: str, errors: list) -> list:
        if not os.path.isdir(folder):
            raise ValueError(f"Folder not found: {folder}")
        tool = load_manifest(folder)
        if tool:
            tool.location = Location("folder", path=folder)
            return [tool]
        for feed_name in FEED_NAMES:
            feed_path = os.path.join(folder, feed_name)
            if os.path.isfile(feed_path):
                data = _read_json_file(feed_path)
                if is_feed(data):
                    return self._index_tools(data, errors, base_dir=folder)
        tools = []
        for entry in sorted(os.listdir(folder)):
            sub = os.path.join(folder, entry)
            if os.path.isfile(os.path.join(sub, MANIFEST_NAME)):
                try:
                    found = load_manifest(sub)
                except ManifestError as exc:
                    errors.append(str(exc))
                    continue
                found.location = Location("folder", path=sub)
                tools.append(found)
        if tools:
            return tools
        tool = scan_folder(folder)
        if tool:
            tool.location = Location("folder", path=folder)
            return [tool]
        return []

    def _resolve(self, ref: str, base_dir: str = "", base_url: str = "") -> str:
        """Resolve a link from a feed: absolute stays as is, relative is taken from the feed's location."""
        ref = normalize_url(ref)
        if is_remote(ref) or _looks_like_path(ref):
            return ref
        if base_url:
            return urljoin(base_url, ref)
        if base_dir:
            return os.path.normpath(os.path.join(base_dir, ref))
        return ref

    def _remote_feed(self, base: str):
        """The first feed file found at a remote folder URL, or None."""
        for feed_name in FEED_NAMES:
            try:
                data = self.http.fetch_json(base + feed_name)
            except NotFound:
                continue
            if is_feed(data):
                return data
        return None

    def _index_tools(self, data, errors: list, base_dir: str = "", base_url: str = "", github=None) -> list:
        tools = []
        for entry in feed_entries(data):
            if isinstance(entry, str):
                entry = {"repo": entry}
            if not isinstance(entry, dict):
                errors.append(f"Skipped a feed entry that isn't an object: {entry!r}")
                continue
            try:
                if "repo" in entry:
                    owner, repo, ref = parse_github(str(entry["repo"]))
                    tools += self._github_tools(owner, repo, str(entry.get("ref") or ref), "", errors)
                elif "url" in entry:
                    url = self._resolve(str(entry["url"]), base_dir, base_url)
                    tools.append(self._feed_tool(entry, url, base_dir, base_url) or self._zip_tool(url))
                elif "path" in entry:
                    rel = str(entry["path"]).replace("\\", "/").strip("/")
                    if github:
                        owner, repo, ref = github
                        tools += self._github_tools(owner, repo, ref, rel, errors)
                    elif base_dir:
                        tools += self._folder_tools(os.path.normpath(os.path.join(base_dir, rel)), errors)
                    else:
                        raise ManifestError('"path" entries only work in a feed in a folder or a GitHub repo')
                else:
                    raise ManifestError(f"Feed entry needs repo, url or path: {entry}")
            except (NetError, ManifestError, ValueError, OSError, zipfile.BadZipFile) as exc:
                errors.append(str(exc))
        return tools

    def _feed_tool(self, entry: dict, url: str, base_dir: str, base_url: str):
        """A tool described by its feed entry, so nothing has to be downloaded to list it."""
        version = str(entry.get("version") or "").strip()
        if not version:
            return None
        name = str(entry.get("name") or "").strip() or _base_name(url)
        tool = ToolInfo(
            id=slugify(str(entry.get("id") or name)),
            name=name,
            version=version,
            description=str(entry.get("description") or ""),
            category=normalize_category(str(entry.get("category") or "Utility")),
            author=str(entry.get("author") or ""),
            homepage=str(entry.get("homepage") or ""),
            own_shelf=bool(entry.get("ownShelf", False)),
            has_manifest=False,
            location=Location("zip", url=url),
        )
        if entry.get("icon"):
            self._cache_preview(tool, self._resolve(str(entry["icon"]), base_dir, base_url))
        return tool

    def _github_tools(self, owner: str, repo: str, ref: str, subdir: str, errors: list) -> list:
        if not ref and not subdir:
            # A feed lives on the default branch so edits show up without making a release.
            head = f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/"
            feed = self._remote_feed(head)
            if feed is not None:
                return self._index_tools(feed, errors, base_url=head, github=(owner, repo, ""))
            try:
                ref = str(self.http.fetch_json(f"https://api.github.com/repos/{owner}/{repo}/releases/latest").get("tag_name") or "")
            except NotFound:
                ref = ""
        raw = f"https://raw.githubusercontent.com/{owner}/{repo}/{ref or 'HEAD'}/" + (subdir + "/" if subdir else "")
        try:
            data = self.http.fetch_json(raw + MANIFEST_NAME)
        except NotFound:
            data = None

        if data is None and ref and not subdir:
            feed = self._remote_feed(raw)
            if feed is not None:
                return self._index_tools(feed, errors, base_url=raw, github=(owner, repo, ref))

        if data is None:
            name = posixpath.basename(subdir) if subdir else repo
            tool = ToolInfo(
                id=slugify(name),
                name=name,
                version=ref.lstrip("vV") if ref else "",
                description="No easytool.json. EasyTool will look for shelves, icons and scripts after downloading.",
                has_manifest=False,
            )
        else:
            tool = parse_manifest(data, fallback_name=posixpath.basename(subdir) if subdir else repo)
            if not tool.version and ref:
                tool.version = ref.lstrip("vV")
            names = [tool.icon] + [b.icon for b in tool.buttons]
            icon = next((n for n in names if n), "")
            if icon:
                self._cache_preview(tool, raw + (tool.icons_dir + "/" if tool.icons_dir else "") + icon)
        tool.location = Location("github", repo=f"{owner}/{repo}", ref=ref, subdir=subdir)
        tool.homepage = tool.homepage or f"https://github.com/{owner}/{repo}"
        return [tool]

    def _cache_preview(self, tool: ToolInfo, src: str) -> None:
        if not is_remote(src):
            if os.path.isfile(src):
                tool.preview_icon = src
            return
        ext = os.path.splitext(urlparse(src).path)[1] or ".png"
        dest = os.path.join(self.cache_dir, "previews", f"{tool.id}-{slugify(tool.version or 'latest')}{ext}")
        if not os.path.isfile(dest):
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            try:
                self.http.download(src, dest)
            except NetError:
                return
        tool.preview_icon = dest

    def _zip_tool(self, url: str) -> ToolInfo:
        """A zip with no version in the feed: download it to see what's inside (every refresh)."""
        folder = self._download_zip(url, cache=False)
        tool = read_tool(folder)
        if tool is None:
            raise ManifestError(f"Found nothing to install in {url}")
        if not tool.has_manifest:
            name = _base_name(url)
            tool.id, tool.name = slugify(name), name
        tool.location = Location("zip", url=url)
        return tool

    # Downloading ---------------------------------------------------------

    def _fetch_file(self, src: str, dest: str) -> None:
        if is_remote(src):
            self.http.download(src, dest)
        elif os.path.isfile(src):
            shutil.copyfile(src, dest)
        else:
            raise ValueError(f"File not found: {src}")

    def _download_zip(self, src: str, version: str = "", cache: bool = True) -> str:
        downloads = os.path.join(self.cache_dir, "downloads")
        target = os.path.join(downloads, _key(f"{src}#{version}"))
        marker = os.path.join(target, ".complete")
        content = os.path.join(target, "content")
        if not (cache and os.path.isfile(marker)):
            if os.path.isdir(target):
                shutil.rmtree(target)
            os.makedirs(content)
            archive = target + ".zip"
            self._fetch_file(src, archive)
            try:
                safe_extract(archive, content)
            finally:
                os.remove(archive)
            open(marker, "w").close()
        return single_child(content)

    def fetch_payload(self, tool: ToolInfo) -> str:
        """Return a local folder holding the tool's files, downloading it if needed."""
        loc = tool.location
        if loc.kind == "folder":
            return loc.path
        if loc.kind == "zip":
            # Cached per version: a new version in the feed means a fresh download.
            return self._download_zip(loc.url, version=tool.version, cache=bool(tool.version))
        if loc.kind == "github":
            url = f"https://api.github.com/repos/{loc.repo}/zipball" + (f"/{loc.ref}" if loc.ref else "")
            folder = self._download_zip(url, cache=bool(loc.ref))
            return os.path.join(folder, loc.subdir) if loc.subdir else folder
        raise ValueError(f"Don't know how to fetch {tool.name}")
