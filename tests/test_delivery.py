"""Delivery numbers: lead time, red-since, release age, quick follow-up releases, flaky checks and stale branches,
computed from invented raw facts."""

import unittest

from everkeep import delivery as D
from everkeep.util import parse_time

TODAY = parse_time("2026-11-13T00:00:00Z")


def run(wf, sha, concl, created, branch="main", attempt=1):
    return {"workflow": wf, "sha": sha, "branch": branch, "conclusion": concl, "created": created, "attempt": attempt}


class Delivery(unittest.TestCase):
    def test_numbers(self):
        raw = {
            "default_branch": "main",
            "merged_prs": [("2026-11-01T00:00:00Z", "2026-11-02T00:00:00Z"), ("2026-11-01T00:00:00Z", "2026-11-05T00:00:00Z"),
                           ("2026-11-01T00:00:00Z", "2026-11-01T12:00:00Z")],
            "runs": [run("ci", "c3", "failure", "2026-11-12T00:00:00Z"), run("ci", "c2", "failure", "2026-11-10T00:00:00Z"),
                     run("ci", "c1", "success", "2026-11-08T00:00:00Z"), run("lint", "c3", "success", "2026-11-12T00:00:00Z"),
                     run("test", "x9", "success", "2026-11-01T00:00:00Z", "feature", attempt=2),
                     run("docs", "d1", "failure", "2026-10-01T00:00:00Z", "feature"),
                     run("docs", "d1", "success", "2026-10-02T00:00:00Z", "feature")],
            "releases": [("v1.0.0", "2026-09-01T00:00:00Z"), ("v1.0.1", "2026-09-02T00:00:00Z"), ("v1.1.0", "2026-10-14T00:00:00Z"), ("v1.2.0", "2026-10-14T01:00:00Z")],
            "unreleased_commits": 7,
            "branches": [("old-idea", "2026-01-01T00:00:00Z"), ("fresh", "2026-11-10T00:00:00Z"),
                         ("dependabot/npm/x-1", "2026-01-01T00:00:00Z"), ("has-pr", "2026-01-01T00:00:00Z")],
            "open_pr_heads": ["has-pr"],
        }
        d = D.compute(raw, TODAY)
        self.assertEqual(d["pr_median_hours"], 24.0)
        self.assertEqual(d["red_since"], "2026-11-10")
        self.assertEqual(d["red_workflows"], ["ci"])
        self.assertEqual(d["flaky"], ["docs", "test"])
        self.assertEqual((d["last_release"], d["release_age_days"], d["fix_release_share"]), ("v1.2.0", 29, "1/3"))
        self.assertEqual(d["stale_branches"], ["old-idea"])
        line = D.line(d)
        self.assertIn("red since 2026-11-10", line)
        self.assertIn("7 commits since", line)

    def test_green_and_empty(self):
        d = D.compute({"default_branch": "main", "runs": [run("ci", "a", "success", "2026-11-12T00:00:00Z"),
                                                           run("ci", "b", "failure", "2026-11-11T00:00:00Z")]}, TODAY)
        self.assertIsNone(d["red_since"])
        self.assertEqual(d["flaky"], [])
        self.assertEqual(D.line(D.compute({}, TODAY)), "no merged PRs, releases or runs seen")


if __name__ == "__main__":
    unittest.main()
