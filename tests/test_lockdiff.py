"""The lockfile-diff checker on real Dependabot diffs (2026-10-13) and synthetic npm, NuGet and Unity cases."""

import unittest

from helpers import FIXTURES
from everkeep import lockdiff


def read(name):
    return (FIXTURES / "diffs" / name).read_text(encoding="utf-8")


NPM_BAD = """diff --git a/package-lock.json b/package-lock.json
--- a/package-lock.json
+++ b/package-lock.json
@@ -10,6 +10,18 @@
     "node_modules/chalk": {
-      "version": "5.3.0",
+      "version": "5.4.0",
+      "hasInstallScript": true,
       "license": "MIT"
     },
+    "node_modules/evil-helper": {
+      "version": "1.0.0",
+      "resolved": "https://registry.npmjs.org/evil-helper/-/evil-helper-1.0.0.tgz"
+    },
+    "node_modules/from-git": {
+      "version": "1.0.0",
+      "resolved": "git+ssh://git@github.com/someone/from-git.git#abc"
+    },
"""

NUGET_CLEAN = """diff --git a/tests/T/packages.lock.json b/tests/T/packages.lock.json
--- a/tests/T/packages.lock.json
+++ b/tests/T/packages.lock.json
@@ -1,12 +1,12 @@
 {
   "version": 1,
   "dependencies": {
     "net10.0": {
       "NUnit3TestAdapter": {
         "type": "Direct",
-        "requested": "[6.3.0, )",
-        "resolved": "6.3.0",
+        "requested": "[6.3.1, )",
+        "resolved": "6.3.1",
"""

UPM = """diff --git a/Packages/packages-lock.json b/Packages/packages-lock.json
--- a/Packages/packages-lock.json
+++ b/Packages/packages-lock.json
@@ -1,4 +1,9 @@
   "dependencies": {
+    "com.someone.tool": {
+      "version": "https://github.com/someone/tool.git",
+      "source": "git"
+    },
"""


class LockDiff(unittest.TestCase):
    def test_nuget_lockfile_that_drops_net48_is_not_clean(self):
        d = lockdiff.analyse(read("nuget-lock-drops-net48.diff"))
        self.assertFalse(d.clean)
        removed = d.files[0].removed_targets
        self.assertIn(".NETFramework,Version=v4.8", removed)
        self.assertIn("net10.0/win-x86", removed)
        self.assertEqual(len(d.files), 2)
        self.assertTrue(any("removed target sections" in r for r in d.reasons))
        # D14 reads the new side's versions: the added package and the ones the bump moves
        self.assertEqual(d.files[0].new_packages, ["Microsoft.TestPlatform.AdapterUtilities"])
        self.assertEqual(d.files[0].versions["Microsoft.TestPlatform.AdapterUtilities"], "18.10.1")
        self.assertEqual(d.files[0].versions["Microsoft.Testing.Platform"], "2.4.1")

    def test_clean_npm_group_bump(self):
        d = lockdiff.analyse(read("npm-group-clean.diff"))
        self.assertTrue(d.clean, d.reasons)
        self.assertEqual(d.files[0].kind, "npm")

    def test_npm_new_package_git_source_and_install_script(self):
        d = lockdiff.analyse(NPM_BAD)
        f = d.files[0]
        self.assertEqual(f.new_packages, ["evil-helper", "from-git"])
        self.assertEqual(f.odd_sources, ["git+ssh://git@github.com/someone/from-git.git#abc"])
        self.assertEqual(f.new_install_scripts, 1)
        self.assertEqual(d.unexpected, ["package-lock.json: git+ssh://git@github.com/someone/from-git.git#abc"])

    def test_nuget_version_only_bump_is_clean(self):
        self.assertTrue(lockdiff.analyse(NUGET_CLEAN).clean)

    def test_unity_git_source_is_flagged(self):
        d = lockdiff.analyse(UPM)
        self.assertEqual(d.files[0].new_packages, ["com.someone.tool"])
        self.assertTrue(d.files[0].odd_sources)

    def test_unread_lockfile_is_never_clean(self):
        d = lockdiff.analyse("diff --git a/yarn.lock b/yarn.lock\n--- a/yarn.lock\n+++ b/yarn.lock\n@@ -1 +1 @@\n-a\n+b\n")
        self.assertFalse(d.clean)
        self.assertIn("not analysed", d.reasons[0])

    def test_non_lockfiles_are_ignored(self):
        self.assertTrue(lockdiff.analyse(read("action-pin-first-party.diff")).clean)


if __name__ == "__main__":
    unittest.main()
