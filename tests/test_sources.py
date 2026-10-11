import io
import os
import unittest
import zipfile

import json

from helpers import EXAMPLES, FakeHttp, TempDirTest, make_legacy_tool, make_module_tool, zip_folder

from easytool.core.models import Location, ToolInfo
from easytool.core.sources import Resolver, Source, detect_kind, make_source, parse_github, safe_extract, single_child

API = "https://api.github.com/repos"
RAW = "https://raw.githubusercontent.com"
MANIFEST = {
    "name": "Pivot Snap",
    "id": "pivot-snap",
    "category": "Modeling",
    "buttons": [{"label": "PIV", "icon": "pivotSnap.png", "command": "import pivot_snap"}],
}


class DetectTest(TempDirTest):
    def test_kinds(self):
        self.assertEqual(detect_kind("https://github.com/studio/pivot-snap"), "github")
        self.assertEqual(detect_kind("github.com/studio/pivot-snap.git"), "github")
        self.assertEqual(detect_kind("studio/pivot-snap"), "github")
        self.assertEqual(detect_kind("https://example.com/tools/index.json"), "index")
        self.assertEqual(detect_kind("https://example.com/dl/tool-1.0.zip?x=1"), "zip")
        self.assertEqual(detect_kind("https://github.com/o/r/releases/download/v1/r.zip"), "zip")
        self.assertEqual(detect_kind(r"D:\pipeline\maya-tools"), "folder")
        self.assertEqual(detect_kind(r"\\studio-nas\maya"), "folder")
        self.assertEqual(detect_kind(self.tmp), "folder")

    def test_rejects_other_links(self):
        with self.assertRaisesRegex(ValueError, "GitHub repo"):
            detect_kind("https://example.com/page")
        with self.assertRaises(ValueError):
            detect_kind("   ")

    def test_parse_github(self):
        self.assertEqual(parse_github("https://github.com/o/r"), ("o", "r", ""))
        self.assertEqual(parse_github("https://github.com/o/r/tree/dev"), ("o", "r", "dev"))
        self.assertEqual(parse_github("https://github.com/o/r/releases/tag/v1.2"), ("o", "r", "v1.2"))
        self.assertEqual(parse_github("o/r@v3"), ("o", "r", "v3"))

    def test_make_source_names(self):
        self.assertEqual(make_source("https://github.com/studio/pivot-snap").name, "pivot-snap")
        self.assertEqual(make_source("https://example.com/maya/index.json").name, "maya")
        self.assertEqual(make_source(r"D:\pipeline\maya-tools").name, "maya-tools")

    def test_github_file_page_links_become_raw_links(self):
        source = make_source("https://github.com/you/maya-tools/blob/main/index.json")
        self.assertEqual(source.url, f"{RAW}/you/maya-tools/main/index.json")
        self.assertEqual((source.kind, source.name), ("index", "maya-tools"))

    def test_local_feed_and_zip_files(self):
        self.assertEqual(detect_kind(r"\\studio-nas\maya\feed.json"), "index")
        self.assertEqual(detect_kind(r"D:\tools\AssignRGB.zip"), "zip")

    def test_source_id_ignores_case(self):
        self.assertEqual(Source("https://GitHub.com/o/r", "github").id, Source("https://github.com/o/r", "github").id)


class ResolverTest(TempDirTest):
    def resolver(self, http=None):
        return Resolver(self.path("cache"), http or FakeHttp())

    def test_local_index_lists_both_examples(self):
        tools = self.resolver().list_tools(make_source(EXAMPLES))
        self.assertEqual([t.id for t in tools], ["pivot-snap", "scene-cleaner"])
        self.assertEqual(tools[0].location.kind, "folder")
        self.assertTrue(tools[0].location.path.endswith("pivot-snap"))

    def test_github_release_with_manifest(self):
        http = FakeHttp(
            json_map={
                f"{API}/studio/pivot-snap/releases/latest": {"tag_name": "v2.1.0"},
                f"{RAW}/studio/pivot-snap/v2.1.0/easytool.json": MANIFEST,
            },
            files={f"{RAW}/studio/pivot-snap/v2.1.0/icons/pivotSnap.png": b"png"},
        )
        [tool] = self.resolver(http).list_tools(make_source("https://github.com/studio/pivot-snap"))
        self.assertEqual(tool.version, "2.1.0")
        self.assertEqual((tool.location.kind, tool.location.repo, tool.location.ref), ("github", "studio/pivot-snap", "v2.1.0"))
        self.assertEqual(tool.homepage, "https://github.com/studio/pivot-snap")
        self.assertTrue(os.path.isfile(tool.preview_icon))

    def test_github_without_release_or_manifest(self):
        [tool] = self.resolver().list_tools(make_source("https://github.com/studio/legacy-shelf"))
        self.assertFalse(tool.has_manifest)
        self.assertEqual(tool.location.ref, "")
        self.assertEqual(tool.name, "legacy-shelf")

    def test_github_repo_with_index_of_subfolders(self):
        http = FakeHttp(json_map={
            f"{RAW}/studio/tools/HEAD/index.json": {"tools": [{"path": "pivot-snap"}]},
            f"{RAW}/studio/tools/HEAD/pivot-snap/easytool.json": MANIFEST,
        })
        [tool] = self.resolver(http).list_tools(make_source("studio/tools"))
        self.assertEqual(tool.location.subdir, "pivot-snap")

    def test_fetch_github_payload_unwraps_zipball(self):
        zipball = zip_folder(os.path.join(EXAMPLES, "pivot-snap"))
        http = FakeHttp(files={f"{API}/studio/pivot-snap/zipball/v1.0.0": zipball})
        resolver = self.resolver(http)
        tool = resolver.list_tools(make_source(EXAMPLES))[0]
        tool.location.kind, tool.location.repo, tool.location.ref = "github", "studio/pivot-snap", "v1.0.0"
        folder = resolver.fetch_payload(tool)
        self.assertTrue(os.path.isfile(os.path.join(folder, "easytool.json")))
        resolver.fetch_payload(tool)  # second call is served from the cache
        self.assertEqual(http.calls.count(f"{API}/studio/pivot-snap/zipball/v1.0.0"), 1)

    def test_zip_source(self):
        url = "https://example.com/dl/scene-cleaner.zip"
        http = FakeHttp(files={url: zip_folder(os.path.join(EXAMPLES, "scene-cleaner"), top="scene-cleaner")})
        [tool] = self.resolver(http).list_tools(make_source(url))
        self.assertEqual((tool.id, tool.location.kind), ("scene-cleaner", "zip"))

    def legacy_zip(self, top=""):
        return zip_folder(make_legacy_tool(self.path("src", "AssignRGB")), top=top)

    def test_feed_with_versions_lists_without_downloading(self):
        feed = f"{RAW}/you/maya-tools/main/index.json"
        http = FakeHttp(
            json_map={feed: {"tools": [
                {"name": "Assign RGB", "version": "1.0.0", "category": "rendering",
                 "url": "tools/AssignRGB.zip", "icon": "icons/AssignRGB.png"},
                {"name": "Private Tool", "version": "2.0.0", "url": "https://example.com/dl/Private.zip"},
            ]}},
            files={f"{RAW}/you/maya-tools/main/icons/AssignRGB.png": b"png"},
        )
        rgb, private = self.resolver(http).list_tools(make_source(feed))
        self.assertEqual((rgb.id, rgb.version, rgb.category), ("assign-rgb", "1.0.0", "Rendering"))
        self.assertEqual(rgb.location.url, f"{RAW}/you/maya-tools/main/tools/AssignRGB.zip")
        self.assertTrue(os.path.isfile(rgb.preview_icon))
        self.assertEqual(private.location.url, "https://example.com/dl/Private.zip")
        self.assertFalse(any(url.endswith(".zip") for url in http.calls))

    def test_repo_feed_comes_from_the_default_branch(self):
        head = f"{RAW}/you/maya-tools/HEAD/"
        http = FakeHttp(json_map={
            head + "index.json": {"tools": [{"url": "tools/AssignRGB.zip", "version": "1.0.0"}]},
            f"{API}/you/maya-tools/releases/latest": {"tag_name": "v0.1"},
        })
        [tool] = self.resolver(http).list_tools(make_source("https://github.com/you/maya-tools"))
        self.assertEqual((tool.name, tool.location.url), ("AssignRGB", head + "tools/AssignRGB.zip"))
        self.assertNotIn(f"{API}/you/maya-tools/releases/latest", http.calls)

    def test_portfolio_site_tools_json_is_a_feed(self):
        head = f"{RAW}/you/Tools/HEAD/"
        site = {
            "schemaVersion": 1,
            "site": {"title": "My Tools", "categories": ["Tools", "Scripts"]},
            "projects": [
                {"id": "batch-rename", "category": "Tools", "title": "Batch Rename", "version": "1.0", "tags": ["Windows"],
                 "enabled": True, "links": [{"label": "Github", "url": "https://github.com/you/BatchRename/releases"}]},
                {"id": "game", "title": "Game", "version": "1.0", "enabled": True,
                 "links": [{"label": "Download", "url": "scripts/Game_v1.0.py"}]},
                {"id": "old", "title": "Old", "version": "1.0", "enabled": False,
                 "links": [{"label": "Download", "url": "scripts/Old.zip"}]},
                {"id": "assign-rgb", "category": "Scripts", "title": "Assign RGB & CMY", "version": "1.1",
                 "desc": "Create and assign RGB & CMY shaders", "tags": ["Maya", "MEL", "Shaders"], "enabled": True,
                 "media": {"type": "icons", "files": ["icons/AssignRGB.png", "icons/AssignRGBCMY.png"]},
                 "links": [{"label": "Download", "url": "scripts/AssignRGB.zip"}]},
            ],
        }
        http = FakeHttp(json_map={head + "tools.json": site}, files={head + "icons/AssignRGB.png": b"png"})
        [tool] = self.resolver(http).list_tools(make_source("https://github.com/you/Tools"))
        self.assertEqual((tool.id, tool.name, tool.version, tool.category),
                         ("assign-rgb", "Assign RGB & CMY", "1.1", "Rendering"))
        self.assertEqual(tool.description, "Create and assign RGB & CMY shaders")
        self.assertEqual(tool.location.url, head + "scripts/AssignRGB.zip")
        self.assertTrue(os.path.isfile(tool.preview_icon))

    def test_new_version_in_the_feed_downloads_again(self):
        url = "https://example.com/dl/AssignRGB.zip"
        http = FakeHttp(files={url: self.legacy_zip()})
        resolver = self.resolver(http)
        tool = ToolInfo(id="assign-rgb", name="Assign RGB", version="1.0.0", location=Location("zip", url=url))
        folder = resolver.fetch_payload(tool)
        self.assertTrue(os.path.isfile(os.path.join(folder, "shelves", "shelf_ColorTools.mel")))
        resolver.fetch_payload(tool)
        self.assertEqual(http.calls.count(url), 1)
        tool.version = "1.1.0"
        resolver.fetch_payload(tool)
        self.assertEqual(http.calls.count(url), 2)

    def test_unversioned_zip_is_checked_on_every_refresh(self):
        url = "https://example.com/dl/AssignRGB.zip"
        http = FakeHttp(files={url: self.legacy_zip()})
        resolver = self.resolver(http)
        [tool] = resolver.list_tools(make_source(url))
        resolver.list_tools(make_source(url))
        self.assertEqual(http.calls.count(url), 2)
        self.assertEqual((tool.id, tool.name, tool.script_files), ("assignrgb", "AssignRGB", ["AssignRGB.mel", "AssignRGBCMY.mel"]))

    def test_local_feed_with_relative_zip(self):
        feed_dir = self.path("feed")
        os.makedirs(feed_dir)
        with open(os.path.join(feed_dir, "AssignRGB.zip"), "wb") as fh:
            fh.write(self.legacy_zip())
        with open(os.path.join(feed_dir, "feed.json"), "w") as fh:
            json.dump({"tools": [{"name": "Assign RGB", "version": "1.0.0", "url": "AssignRGB.zip"}]}, fh)
        resolver = self.resolver()
        [tool] = resolver.list_tools(make_source(os.path.join(feed_dir, "feed.json")))
        self.assertEqual(tool.location.url, os.path.join(feed_dir, "AssignRGB.zip"))
        folder = resolver.fetch_payload(tool)
        self.assertTrue(os.path.isfile(os.path.join(folder, "AssignRGB.mel")))

    def test_list_all_reports_errors_per_source(self):
        good = make_source(EXAMPLES)
        bad = Source("https://example.com/missing/index.json", "index", "missing")
        off = Source(r"D:\nowhere", "folder", "off", enabled=False)
        results = self.resolver().list_all([good, bad, off])
        self.assertEqual(len(results), 2)
        self.assertEqual(len(results[0].tools), 2)
        self.assertEqual(results[0].tools[0].source_id, good.id)
        self.assertTrue(results[1].errors)


class LayoutSourcesTest(TempDirTest):
    def resolver(self, http=None):
        return Resolver(self.path("cache"), http or FakeHttp())

    def test_unwraps_nested_top_folders_but_not_tool_folders(self):
        self.write("a/Tool-1.0/Tool/Tool.mod", "+ Tool 1.0 .")
        self.assertEqual(single_child(self.path("a")), self.path("a", "Tool-1.0", "Tool"))
        self.write("b/scripts/tool.mel")
        self.assertEqual(single_child(self.path("b")), self.path("b"))
        self.write("c/wrap/my_tool/__init__.py")
        self.assertEqual(single_child(self.path("c")), self.path("c", "wrap"))

    def test_zip_of_a_module_in_wrapper_folders(self):
        url = "https://example.com/dl/Build-1.0.zip"
        make_module_tool(self.path("src", "Build"))
        http = FakeHttp(files={url: zip_folder(self.path("src"), top="Build-1.0")})
        [tool] = self.resolver(http).list_tools(make_source(url))
        self.assertEqual((tool.id, tool.module, tool.version, len(tool.buttons)), ("build-1-0", True, "1.0", 1))

    def test_zip_of_just_a_python_package(self):
        url = "https://example.com/dl/my_tool.zip"
        self.write("src/my_tool/__init__.py")
        self.write("src/my_tool/ui.py")
        http = FakeHttp(files={url: zip_folder(self.path("src"), top="")})
        [tool] = self.resolver(http).list_tools(make_source(url))
        self.assertEqual(tool.script_files, ["my_tool"])

    def test_folder_of_modules(self):
        make_module_tool(self.path("share", "Build"))
        self.write("share/Other/other.mod", "+ other 3.0 .")
        self.write("share/Other/scripts/other.py")
        build, other = self.resolver().list_tools(make_source(self.path("share")))
        self.assertEqual((build.name, other.name, other.version), ("Build", "Other", "3.0"))
        self.assertEqual(other.location.path, self.path("share", "Other"))
        [one] = self.resolver().list_tools(make_source(self.path("share", "Build")))  # a module is one tool
        self.assertEqual(one.mod_files, ["build_modifier.mod"])

    def test_github_subfolder_is_relative_to_the_repo(self):
        self.write("repo/tools/pivot-snap/easytool.json", json.dumps({"name": "Pivot Snap"}))
        self.write("repo/tools/pivot-snap/scripts/pivot_snap.py")
        url = f"{API}/studio/repo/zipball/v1"
        http = FakeHttp(files={url: zip_folder(self.path("repo"))})
        tool = ToolInfo(id="pivot-snap", name="Pivot Snap", location=Location("github", repo="studio/repo", ref="v1", subdir="tools/pivot-snap"))
        folder = self.resolver(http).fetch_payload(tool)
        self.assertTrue(os.path.isfile(os.path.join(folder, "easytool.json")))


class SafeExtractTest(TempDirTest):
    def test_refuses_paths_outside_destination(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("../evil.txt", "nope")
        archive = self.write("evil.zip", buf.getvalue())
        with self.assertRaisesRegex(ValueError, "Unsafe path"):
            safe_extract(archive, self.path("out"))
        self.assertFalse(os.path.exists(self.path("evil.txt")))


if __name__ == "__main__":
    unittest.main()
