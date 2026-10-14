"""The state store, outside any repository: ~/.everkeep (EVERKEEP_HOME overrides).

    config.json            providers, accounts, hosts, clone map, defaults (merged over DEFAULTS)
    overlay/               the user's private overlay (EVERKEEP_OVERLAY overrides): overlay.json merged last, OVERLAY.md for the model
    selections.json        saved selections (a filter, or a frozen list)
    state/<provider>/<owner>/<repo>.json   per-repo memory: last run per duty, decisions with PR and head SHA
    runs/<run-id>/run.json                 a resumable multi-repo run; repos/<slug>.json holds each repo's facts
Every write goes through util.atomic_write."""

from __future__ import annotations

import copy
import os
import random
import string
from pathlib import Path

from .util import EverkeepError, home, iso, now, read_json, slug, write_json

DEFAULTS: dict = {
    "accounts": {},  # {"github": ["some-org"]}: extra accounts beyond the logged-in one
    "hosts": {},  # {"git.example.com": "gitea"}: pins a host to a provider
    "include": {"forks": False, "archived": False, "private": False},
    "learn": False,
    "escalate_to": None,  # default: the logged-in account
    "cooldown": {"days": 3, "major_days": 7},
    "caps": {"merges_per_repo": 3, "merges_per_run": 10, "closes_per_run": 5, "writes_per_hour": 300,
             "open_everkeep_prs_per_repo": 2},
    "tiers": {"high": [], "shared": [], "thresholds": {"total": 100000, "recent": 2000}},
    "packages": {},  # {"repo-name": ["nuget:Package.Id", "npm:name"]}
    "downloads_csv": None,  # repo-traffic's data/downloads.csv
    "clones": {},  # {"github:owner/name": "/path/to/clone"}
    "clone_roots": [],  # folders whose children are clones, matched by name then origin
    "small_pr_lines": 200,
    "compromised": [],  # ["package@version", ...] that stop a run from widening
    "private_runner": {"doctor": None},
    "duties": ["prs", "vulns", "gaps", "kb"],
    "everlast": None,  # path to everlast.py
    "kb_sync": "pr",  # everlast --sync for a new knowledge base in mode repo
    "kb_private": "repo",  # "excluded" keeps private repos' knowledge bases out of the repo
    "package_modernize": None,  # path to the package-modernize skill folder
}


def _merge(base: dict, extra: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


class Store:
    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root else home()
        self._config: dict | None = None

    # ------------------------------------------------------------ config and overlay

    @property
    def overlay_dir(self) -> Path:
        env = os.environ.get("EVERKEEP_OVERLAY")
        if env:
            p = Path(env)
            return p.parent if p.is_file() else p
        return self.root / "overlay"

    def config(self) -> dict:
        if self._config is None:
            cfg = _merge(DEFAULTS, read_json(self.root / "config.json", {}) or {})
            cfg = _merge(cfg, read_json(self.overlay_dir / "overlay.json", {}) or {})
            self._config = cfg
        return self._config

    def overlay_text(self) -> str | None:
        p = self.overlay_dir / "OVERLAY.md"
        return p.read_text(encoding="utf-8") if p.exists() else None

    # ------------------------------------------------------------ selections

    def selections(self) -> dict:
        sel = dict((self.config().get("selections") or {}))  # the overlay's starter selections
        sel.update(read_json(self.root / "selections.json", {}) or {})
        return sel

    def save_selection(self, name: str, spec: dict) -> Path:
        data = read_json(self.root / "selections.json", {}) or {}
        data[name] = spec
        write_json(self.root / "selections.json", data)
        return self.root / "selections.json"

    # ------------------------------------------------------------ per-repo state

    def repo_path(self, repo_id: str) -> Path:
        provider, _, path = repo_id.partition(":")
        if "@" in provider:
            provider, host = provider.split("@", 1)
            provider = f"{provider}@{slug(host)}"
        return self.root / "state" / provider / Path(*[slug(p) for p in path.split("/")]).with_suffix(".json")

    def repo_state(self, repo_id: str) -> dict:
        return read_json(self.repo_path(repo_id), {"repo": repo_id, "duties": {}, "decisions": []})

    def save_repo_state(self, repo_id: str, data: dict) -> None:
        write_json(self.repo_path(repo_id), data)

    def record_decision(self, repo_id: str, decision: dict) -> None:
        st = self.repo_state(repo_id)
        st.setdefault("decisions", []).append({**decision, "at": iso(now())})
        st["decisions"] = st["decisions"][-200:]
        self.save_repo_state(repo_id, st)

    def forget(self, repo_id: str) -> bool:
        p = self.repo_path(repo_id)
        if p.exists():
            p.unlink()
            return True
        return False

    # ------------------------------------------------------------ runs

    def run_dir(self, run_id: str) -> Path:
        return self.root / "runs" / run_id

    def new_run(self, entries: list[dict], duties: list[str], scope: dict, learn: bool, apply: bool) -> dict:
        rid = now().strftime("%Y%m%d-%H%M%S") + "-" + "".join(random.choices(string.ascii_lowercase, k=4))
        run = {"id": rid, "created": iso(now()), "scope": scope, "duties": duties, "learn": learn, "apply": apply,
               "stopped": None,
               "repos": [{"id": e["id"], "tier": e.get("tier"), "status": "pending", "reason": "", "updated": None}
                         for e in entries]}
        self.save_run(run)
        return run

    def load_run(self, run_id: str) -> dict:
        if run_id == "latest":
            runs = sorted((self.root / "runs").glob("*/run.json"))
            if not runs:
                raise EverkeepError("no runs yet")
            run_id = runs[-1].parent.name
        run = read_json(self.run_dir(run_id) / "run.json")
        if run is None:
            raise EverkeepError(f"no run {run_id} under {self.root / 'runs'}")
        return run

    def save_run(self, run: dict) -> None:
        write_json(self.run_dir(run["id"]) / "run.json", run)

    def mark(self, run: dict, repo_id: str, status: str, reason: str = "") -> None:
        for r in run["repos"]:
            if r["id"] == repo_id:
                r["status"], r["reason"], r["updated"] = status, reason, iso(now())
        self.save_run(run)

    def save_facts(self, run: dict, repo_id: str, facts: dict) -> Path:
        p = self.run_dir(run["id"]) / "repos" / (slug(repo_id) + ".json")
        write_json(p, facts)
        return p

    def load_facts(self, run: dict, repo_id: str) -> dict | None:
        return read_json(self.run_dir(run["id"]) / "repos" / (slug(repo_id) + ".json"))
