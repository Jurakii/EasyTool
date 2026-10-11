import os
import unittest
from unittest import mock

from helpers import TempDirTest

from easytool.core import selfupdate
from easytool.core.models import ToolInfo
from easytool.core.selfupdate import UpdateError, apply_update, find_package, is_source_checkout, pick_update, read_version


class SelfUpdateTest(TempDirTest):
    def make_package(self, rel, version, extra=None):
        self.write(f"{rel}/easytool/__init__.py", f'"""EasyTool."""\n\n__version__ = "{version}"\n')
        self.write(f"{rel}/easytool/core/models.py", "X = 1\n")
        for name in extra or []:
            self.write(f"{rel}/easytool/{name}", "")
        return self.path(*rel.split("/"), "easytool")

    def test_finds_the_package_in_a_release(self):
        self.make_package("release", "1.2.0")
        self.assertEqual(read_version(find_package(self.path("release"))), "1.2.0")
        self.make_package("other/scripts", "1.0.0")
        self.assertTrue(find_package(self.path("other")).endswith(os.path.join("scripts", "easytool")))
        os.makedirs(self.path("empty"))
        with self.assertRaises(UpdateError):
            find_package(self.path("empty"))

    def test_swaps_the_installed_copy(self):
        installed = self.make_package("maya/scripts", "0.1.0", extra=["removed_in_new.py"])
        self.make_package("release", "0.2.0")
        self.assertEqual(apply_update(self.path("release"), installed, "0.1.0"), "0.2.0")
        self.assertEqual(read_version(installed), "0.2.0")
        self.assertFalse(os.path.exists(os.path.join(installed, "removed_in_new.py")))
        self.assertEqual(os.listdir(self.path("maya", "scripts")), ["easytool"])  # no leftovers

    def test_refuses_a_version_that_isnt_newer(self):
        installed = self.make_package("maya/scripts", "0.2.0")
        self.make_package("release", "0.2.0")
        with self.assertRaisesRegex(UpdateError, "isn't newer"):
            apply_update(self.path("release"), installed, "0.2.0")
        self.assertEqual(read_version(installed), "0.2.0")

    def test_never_overwrites_a_source_checkout(self):
        repo_copy = self.make_package("repo", "0.1.0")
        self.write("repo/drag_into_maya.py", "")
        self.make_package("release", "0.2.0")
        self.assertTrue(is_source_checkout(repo_copy))
        with self.assertRaisesRegex(UpdateError, "Update that copy from its repo"):
            apply_update(self.path("release"), repo_copy, "0.1.0")
        self.assertEqual(read_version(repo_copy), "0.1.0")

    def test_puts_the_old_copy_back_if_the_swap_fails(self):
        installed = self.make_package("maya/scripts", "0.1.0")
        self.make_package("release", "0.2.0")
        real_rename = os.rename
        calls = []

        def flaky_rename(src, dst):
            calls.append(src)
            if len(calls) == 2:  # moving the new copy into place
                raise PermissionError(13, "in use")
            real_rename(src, dst)

        with mock.patch.object(selfupdate.os, "rename", flaky_rename):
            with self.assertRaisesRegex(UpdateError, "Nothing was changed"):
                apply_update(self.path("release"), installed, "0.1.0")
        self.assertEqual(read_version(installed), "0.1.0")
        self.assertEqual(os.listdir(self.path("maya", "scripts")), ["easytool"])

    def test_only_the_update_source_can_offer_an_update(self):
        tools = [
            ToolInfo(id="easytool", name="EasyTool", version="0.3.0", source_id="someone-else"),
            ToolInfo(id="easytool", name="EasyTool", version="0.2.0", source_id="mine"),
            ToolInfo(id="pivot-snap", name="Pivot Snap", version="9.0.0", source_id="mine"),
        ]
        self.assertEqual(pick_update(tools, "mine", "0.1.0").version, "0.2.0")
        self.assertIsNone(pick_update(tools, "mine", "0.2.0"))


if __name__ == "__main__":
    unittest.main()
