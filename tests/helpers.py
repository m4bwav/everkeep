"""Shared test setup: the CLI package on sys.path, a pinned clock, a throwaway state folder, a fake registry."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "everkeep" / "scripts"
FIXTURES = ROOT / "tests" / "fixtures"
sys.path.insert(0, str(SCRIPTS))

from everkeep import registries  # noqa: E402
from everkeep.providers import registry  # noqa: E402

NOW = "2026-10-14T00:00:00Z"


def _npm(times: dict, publisher="GitHub Actions", trusted=True, overrides=None):
    versions = {v: {"_npmUser": {"name": publisher, **({"trustedPublisher": {"id": "github"}} if trusted else {})}} for v in times}
    versions.update(overrides or {})
    return {"time": times, "versions": versions, "dist-tags": {"latest": list(times)[-1]}}


REGISTRY = {
    "https://registry.npmjs.org/@types%2Fnode": _npm({"24.19.0": "2026-09-01T00:00:00Z", "24.19.1": "2026-10-01T00:00:00Z"}),
    "https://registry.npmjs.org/publint": _npm({"0.3.24": "2026-08-19T06:40:11.452Z", "0.3.25": "2026-10-01T18:03:33.533Z"}),
    "https://registry.npmjs.org/left-pad-x": _npm({"1.0.0": "2025-01-01T00:00:00Z", "1.0.1": "2026-10-13T12:00:00Z"}),
    "https://api.nuget.org/v3/registration5-gz-semver2/nunit3testadapter/index.json":
        {"items": [{"items": [{"catalogEntry": {"version": "6.3.1", "published": "2026-10-09T20:22:50.37+00:00"}}]}]},
}


def fake_fetch(url, timeout=20):
    if url in REGISTRY:
        return REGISTRY[url]
    raise registries.FetchError(f"{url}: not in the test registry")


class EnvCase(unittest.TestCase):
    """Each test gets its own state folder, the fake account, the fake registry and a pinned clock."""

    fixture = FIXTURES / "account.json"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        env = {"EVERKEEP_HOME": str(self.home), "EVERKEEP_NOW": NOW, "EVERKEEP_FAKE_PROVIDER": str(self.fixture),
               "EVERKEEP_OVERLAY": str(self.home / "overlay")}
        self.env = mock.patch.dict(os.environ, env)
        self.env.start()
        os.environ.pop("EVERKEEP_INTERRUPT_AFTER", None)
        self.fetch = mock.patch.object(registries, "fetch_json", fake_fetch)
        self.fetch.start()
        registry.reset_cache()

    def tearDown(self):
        self.fetch.stop()
        self.env.stop()
        registry.reset_cache()
        self.tmp.cleanup()

    def write_config(self, data):
        import json
        (self.home).mkdir(parents=True, exist_ok=True)
        (self.home / "config.json").write_text(json.dumps(data), encoding="utf-8")

    def provider(self):
        return registry.get_provider("github")
