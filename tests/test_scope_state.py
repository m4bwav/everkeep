"""Scope resolution and filters, tiers, saved selections, atomic writes, and resumable runs."""

import argparse
import os
import unittest
from pathlib import Path

from helpers import EnvCase
from everkeep import runs as R
from everkeep import scope as S
from everkeep.state import Store
from everkeep.util import atomic_write, read_json, write_json


def args(**kw):
    ns = argparse.Namespace(repo=[], select=None, filter=[], all=False, include_forks=False, include_archived=False,
                            include_private=False, exclude_private=False)
    for k, v in kw.items():
        setattr(ns, k, v)
    return ns


class Scope(EnvCase):
    def ids(self, **kw):
        return [e["id"] for e in S.resolve(args(**kw), Store())]

    def test_all_excludes_forks_and_private_by_default(self):
        got = self.ids(all=True)
        self.assertNotIn("github:owner/fork-x", got)
        self.assertNotIn("github:owner/private-site", got)
        self.assertIn("github:owner/npm-lib", got)

    def test_include_flags_and_overlay_default(self):
        self.assertIn("github:owner/fork-x", self.ids(all=True, include_forks=True))
        self.write_config({"include": {"private": True}})
        self.assertIn("github:owner/private-site", self.ids(all=True))
        self.assertNotIn("github:owner/private-site", self.ids(all=True, exclude_private=True))

    def test_repo_names_resolve_against_the_logged_in_account(self):
        self.assertEqual(self.ids(repo=["npm-lib", "owner/nuget-lib"]), ["github:owner/npm-lib", "github:owner/nuget-lib"])

    def test_filters_are_anded(self):
        self.assertEqual(self.ids(filter=["ecosystem=npm", "visibility=public"]), ["github:owner/npm-lib"])
        self.assertEqual(self.ids(filter=["ecosystem=nuget"]), ["github:owner/nuget-lib", "github:owner/popular"])
        self.assertEqual(self.ids(filter=["name=nuget-*"]), ["github:owner/nuget-lib"])
        self.assertEqual(self.ids(filter=["visibility=private"]), ["github:owner/private-site"])
        self.assertEqual(self.ids(filter=["has=failing-prs", "visibility=public"]), ["github:owner/nuget-lib"])
        self.assertEqual(self.ids(filter=["name=npm-lib,nuget-lib"]), ["github:owner/npm-lib", "github:owner/nuget-lib"])

    def test_bad_filter_key_is_an_error(self):
        with self.assertRaises(Exception):
            self.ids(filter=["colour=blue"])

    def test_risk_order_low_then_medium_then_high(self):
        self.write_config({"tiers": {"high": ["Popular"]}})
        entries = S.resolve(args(all=True), Store())
        tiers = [e["tier"] for e in entries]
        self.assertEqual(tiers, sorted(tiers, key=lambda t: S.TIER_RANK[t]))
        self.assertEqual(entries[-1]["id"], "github:owner/popular")

    def test_tiers(self):
        self.write_config({"tiers": {"high": ["Popular"]}})
        by = {e["id"]: e["tier"] for e in S.resolve(args(all=True, include_forks=True, include_private=True), Store())}
        self.assertEqual(by["github:owner/popular"], "high")
        self.assertEqual(by["github:owner/fork-x"], "shared")
        self.assertEqual(by["github:owner/npm-lib"], "medium")
        self.assertEqual(by["github:owner/private-site"], "low")  # its package.json is private

    def test_download_thresholds_make_a_package_high(self):
        csv = self.home / "downloads.csv"
        csv.write_text("snapshot,registry,package,last_14_days,last_month,last_6_weeks,total\n"
                       "2026-10-13,npm,npm-lib,10,20,,150000\n", encoding="utf-8")
        self.write_config({"downloads_csv": str(csv)})
        self.assertEqual(S.resolve(args(repo=["npm-lib"]), Store())[0]["tier"], "high")

    def test_registry_ownership(self):
        import helpers
        helpers.REGISTRY["https://registry.npmjs.org/gone-pkg"] = {"name": "gone-pkg", "time": {"unpublished": {}}}
        helpers.REGISTRY["https://registry.npmjs.org/theirs"] = {"versions": {"1.0.0": {}}, "maintainers": [{"name": "someone"}]}
        helpers.REGISTRY["https://registry.npmjs.org/mine"] = {"versions": {"1.0.0": {}}, "maintainers": [{"name": "me"}]}
        try:
            self.assertFalse(S._on_registry("npm:gone-pkg", {}))  # unpublished long ago
            self.assertFalse(S._on_registry("npm:theirs", {"npm": ["me"]}))  # a name someone else owns
            self.assertTrue(S._on_registry("npm:mine", {"npm": ["me"]}))
            self.assertTrue(S._on_registry("npm:theirs", {}))  # no accounts configured: existence is enough
            self.assertIsNone(S._on_registry("npm:offline-pkg", {}))  # could not ask: kept, never dropped
        finally:
            for k in ("gone-pkg", "theirs", "mine"):
                helpers.REGISTRY.pop("https://registry.npmjs.org/" + k)

    def test_package_filter_means_publishes_there(self):
        self.assertEqual(self.ids(filter=["package=nuget"]), ["github:owner/nuget-lib", "github:owner/popular"])

    def test_saved_selection_stores_the_filter_so_new_repos_join(self):
        store = Store()
        store.save_selection("nuget", {"filter": ["ecosystem=nuget"]})
        self.assertIn("github:owner/nuget-lib", [e["id"] for e in S.resolve(args(select="nuget"), store)])
        with self.assertRaises(Exception):
            S.resolve(args(select="nope"), store)


class StateAndRuns(EnvCase):
    def test_atomic_write_leaves_no_temp_files(self):
        p = self.home / "a" / "b.json"
        write_json(p, {"x": 1})
        atomic_write(p, '{"x": 2}\n')
        self.assertEqual(read_json(p), {"x": 2})
        self.assertEqual([f.name for f in p.parent.iterdir()], ["b.json"])

    def start(self, duties=("prs", "gaps")):
        store = Store()
        entries = S.resolve(args(all=True), store)
        return store, store.new_run(entries, list(duties), {"all": True}, False, False)

    def test_interrupted_run_resumes_from_the_first_pending_repo(self):
        store, run = self.start()
        total = len(run["repos"])
        os.environ["EVERKEEP_INTERRUPT_AFTER"] = "1"
        with self.assertRaises(KeyboardInterrupt):
            R.process(run, store, echo=lambda m: None)
        del os.environ["EVERKEEP_INTERRUPT_AFTER"]
        run = store.load_run(run["id"])
        self.assertEqual(R.summary(run), {"done": 1, "pending": total - 1})
        first = run["repos"][0]["id"]
        R.process(store.load_run(run["id"]), store, echo=lambda m: None)
        run = store.load_run(run["id"])
        self.assertEqual(R.summary(run).get("pending"), None)
        self.assertEqual(run["repos"][0]["id"], first)  # the frozen order holds
        self.assertTrue(store.load_facts(run, first))

    def test_max_limits_one_call(self):
        store, run = self.start()
        R.process(run, store, max_repos=2, echo=lambda m: None)
        self.assertEqual(R.summary(store.load_run(run["id"]))["done"], 2)

    def test_failed_repos_retry_only_with_failed(self):
        store, run = self.start()
        run["repos"][0]["status"], run["repos"][0]["reason"] = "failed", "boom"
        store.save_run(run)
        R.process(run, store, echo=lambda m: None)
        run = store.load_run(run["id"])
        self.assertEqual(run["repos"][0]["status"], "failed")
        R.process(R.resume(run, store, failed=True, release_held=False), store, echo=lambda m: None)
        self.assertEqual(store.load_run(run["id"])["repos"][0]["status"], "done")

    def test_unexpected_finding_stops_widening_and_holds_the_rest(self):
        self.write_config({"compromised": ["publint@0.3.25"]})
        store, run = self.start(("prs",))
        R.process(run, store, echo=lambda m: None)
        run = store.load_run(run["id"])
        self.assertTrue(run["stopped"])
        statuses = [r["status"] for r in run["repos"]]
        self.assertIn("held", statuses)
        R.process(R.resume(run, store, failed=False, release_held=True), store, echo=lambda m: None)
        self.assertNotIn("held", [r["status"] for r in store.load_run(run["id"])["repos"]])

    def test_repo_state_records_last_run(self):
        store, run = self.start(("gaps",))
        R.process(run, store, echo=lambda m: None)
        st = store.repo_state(run["repos"][0]["id"])
        self.assertEqual(st["duties"]["gaps"]["run"], run["id"])
        self.assertTrue(Path(store.repo_path(run["repos"][0]["id"])).exists())


if __name__ == "__main__":
    unittest.main()
