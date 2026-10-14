"""act: guards re-checked at the moment of acting, learning mode, caps, sticky verdict comments, safe public text."""

import unittest

from helpers import EnvCase
from everkeep import act as A
from everkeep import verdict as V
from everkeep.state import Store


def item(repo, pr, sha, verdict, **kw):
    return {"repo": f"github:{repo}", "pr": pr, "head_sha": sha, "verdict": verdict, **kw}


NPM9 = "7722dc2768b1b4db52cf06e5b54a049bcc484ca9"
PIN10 = "0eaaad7730810fc85b8dafd637fb3a4152f47296"


class Act(EnvCase):
    def run_plan(self, items, apply=True, learn=None):
        return A.execute({"items": items}, Store(), apply=apply, learn=learn)

    def test_merge_refused_when_head_moved_after_review(self):
        res = self.run_plan([item("owner/npm-lib", 9, "f" * 40, "merge")])[0]
        self.assertIn("head moved", res["refused"])
        self.assertEqual(self.provider().writes, [])

    def test_merge_allowed_at_the_judged_sha(self):
        res = self.run_plan([item("owner/nuget-lib", 10, PIN10, "merge")])[0]
        self.assertIsNone(res["refused"], res)
        merges = [w for w in self.provider().writes if w["kind"] == "merge"]
        self.assertEqual(len(merges), 1)
        self.assertIn(PIN10[:12], merges[0]["detail"])

    def test_dry_run_writes_nothing(self):
        res = self.run_plan([item("owner/nuget-lib", 10, PIN10, "merge")], apply=False)[0]
        self.assertIsNone(res["refused"])
        self.assertFalse(res["actions"][0]["applied"])
        self.assertEqual(self.provider().writes, [])

    def test_model_cannot_merge_against_the_table(self):
        res = self.run_plan([item("owner/nuget-lib", 13, "4" * 40, "merge")])[0]
        self.assertIn("the table now says escalate", res["refused"])

    def test_learning_mode_only_comments(self):
        res = self.run_plan([item("owner/nuget-lib", 10, PIN10, "merge")], learn=True)[0]
        kinds = [w["kind"] for w in self.provider().writes]
        self.assertEqual(kinds, ["verdict"])
        self.assertIn("Would merge", self.provider().writes[0]["body"])
        self.assertIn(V.LEARN_NOTE, self.provider().writes[0]["body"])
        self.assertTrue(res["learn"])

    def test_verdict_comment_is_sticky(self):
        self.run_plan([item("owner/npm-lib", 11, "2" * 40, "hold")])
        self.run_plan([item("owner/npm-lib", 11, "2" * 40, "escalate")])
        comments = [c for c in self.provider()._pr(*self._rid("owner/npm-lib", 11)).get("comments", []) if V.MARKER in c["body"]]
        self.assertEqual(len(comments), 1)
        self.assertIn("Waiting for the maintainer", comments[0]["body"])

    def _rid(self, repo, n):
        from everkeep.providers.base import RepoId
        return RepoId("github", repo), n

    def test_hold_comment_names_the_date(self):
        self.run_plan([item("owner/npm-lib", 11, "2" * 40, "hold")])
        body = self.provider().writes[0]["body"]
        self.assertIn("Holding until 2026-10-16", body)
        self.assertIn("cooldown is 3 days", body)

    def test_escalate_assigns_labels_and_requests_review_from_the_maintainer(self):
        self.run_plan([item("owner/nuget-lib", 13, "4" * 40, "escalate")])
        kinds = [w["kind"] for w in self.provider().writes]
        for k in ("verdict", "label", "assign", "review"):
            self.assertIn(k, kinds)

    def test_human_close_needs_the_model_read_and_a_rule(self):
        res = self.run_plan([item("owner/npm-lib", 10, "1" * 40, "close")])[0]
        self.assertIn("confirmed_by_reading", res["refused"])
        res = self.run_plan([item("owner/npm-lib", 10, "1" * 40, "close", confirmed_by_reading=True, rule="no-churn")])[0]
        self.assertIsNone(res["refused"], res)
        body = next(w for w in self.provider().writes if w["kind"] == "comment")["body"]
        self.assertIn("unrequested refactors", body)
        self.assertNotIn("AI", body.split("<sub>")[0])  # a close never calls the PR AI-made

    def test_close_cap(self):
        self.write_config({"caps": {"closes_per_run": 0}})
        res = self.run_plan([item("owner/npm-lib", 10, "1" * 40, "close", confirmed_by_reading=True, rule="spam")])[0]
        self.assertIn("cap", res["refused"])

    def test_merge_cap_per_run(self):
        self.write_config({"caps": {"merges_per_run": 0}})
        res = self.run_plan([item("owner/nuget-lib", 10, PIN10, "merge")])[0]
        self.assertIn("cap", res["refused"])

    def test_draft_plan_maps_the_table(self):
        from everkeep import prs, scope
        from everkeep.providers.base import RepoId
        store = Store()
        entry = scope.describe(self.provider().get_repo(RepoId("github", "owner/npm-lib")), store)
        plan = A.draft_plan(prs.gather_repo(entry, store.config()), learn=True)
        by = {i["pr"]: i for i in plan["items"]}
        self.assertEqual(by[9]["verdict"], "merge")
        self.assertEqual(by[10]["verdict"], "escalate")  # recommend close, the model decides
        self.assertEqual(by[12]["verdict"], "skip")
        self.assertTrue(plan["learn"])


class PublicText(unittest.TestCase):
    def test_public_strips_markup(self):
        self.assertEqual(V.public("see [x](http://e) <img src=x> `y`"), "see x(http://e) img src=x y")

    def test_human_pr_reasons_lose_their_paths(self):
        facts = {"bot": None, "tier": "low", "classification": {"class": "escalate", "hold_until": None,
                                                                   "reasons": ["touches executed config: .github/workflows/please-merge.yml"]}}
        body = V.verdict_body(facts, "escalate", False)
        self.assertNotIn("please-merge", body)
        self.assertIn("touches executed config", body)


if __name__ == "__main__":
    unittest.main()
