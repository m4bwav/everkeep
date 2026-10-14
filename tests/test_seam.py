"""The seam: prs classification, gaps and the digest run end to end through the fake adapter with gh removed from
PATH, so nothing above the provider interface depends on gh. A GitLab clone gets "not supported yet" and exit 3."""

import contextlib
import io
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from helpers import EnvCase
from everkeep import cli


def keep(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = cli.main(list(argv))
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class Seam(EnvCase):
    def setUp(self):
        super().setUp()
        shims = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, shims, True)
        git = self.git = shutil.which("git")
        # PATH holds one folder with a git shim (for the GitLab case) and nothing else: no gh anywhere, even on
        # runners where gh sits beside git in /usr/bin.
        if git:
            if os.name == "nt":
                Path(shims, "git.cmd").write_text(f'@"{git}" %*\r\n', encoding="utf-8")
            else:
                shim = Path(shims, "git")
                shim.write_text(f'#!/bin/sh\nexec "{git}" "$@"\n', encoding="utf-8")
                shim.chmod(0o755)
        os.environ["PATH"] = shims

    def test_gh_is_really_gone(self):
        self.assertIsNone(shutil.which("gh"))

    def test_prs_classification_through_the_fake_adapter(self):
        code, out, err = keep("prs", "--all", "--json")
        self.assertEqual(code, 0, err)
        import json
        data = json.loads(out)
        classes = {f"{f['repo']}#{f['number']}": f["classification"]["class"] for f in data["prs"]}
        self.assertEqual(classes["github:owner/npm-lib#9"], "merge-candidate")
        self.assertEqual(classes["github:owner/nuget-lib#12"], "fix")
        self.assertEqual(classes["github:owner/nuget-lib#13"], "escalate")

    def test_gaps_through_the_fake_adapter(self):
        code, out, err = keep("gaps", "--repo", "owner/nuget-lib")
        self.assertEqual(code, 0, err)
        self.assertIn("| SECURITY.md | gap |", out)
        self.assertIn("actions/checkout@v4", out)
        self.assertIn("2026-11-02", out)  # pull_request_target deadline
        self.assertIn("2026-11-01", out)  # NuGet key deadline
        self.assertIn("2026-11-10", out)  # net8.0

    def test_run_and_digest_through_the_fake_adapter(self):
        code, out, err = keep("run", "start", "--all", "--duties", "prs,gaps")
        self.assertEqual(code, 0, err)
        code, out, err = keep("report", "latest")
        self.assertEqual(code, 0, err)
        self.assertIn("### Would merge", out)
        self.assertIn("### Needs a fix", out)
        self.assertIn("### Would wait for the maintainer", out)
        self.assertIn("## Deadlines", out)
        self.assertTrue(list(Path(self.home, "runs").glob("*/digest.md")))

    def test_gitlab_clone_is_not_supported_and_does_nothing_else(self):
        if not self.git:
            self.skipTest("git not installed")
        repo = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, repo, True)
        subprocess.run([self.git, "init", "-q", repo], check=True)
        subprocess.run([self.git, "-C", repo, "remote", "add", "origin", "https://gitlab.com/group/sub/project.git"], check=True)
        cwd = os.getcwd()
        os.chdir(repo)
        try:
            code, out, err = keep("prs")
        finally:
            os.chdir(cwd)
        self.assertEqual(code, 3)
        self.assertIn("provider gitlab isn't supported yet", err)
        self.assertEqual(out, "")
        self.assertFalse((self.home / "runs").exists())


if __name__ == "__main__":
    unittest.main()
