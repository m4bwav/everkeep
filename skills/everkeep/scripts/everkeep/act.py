"""`keep.py act PLAN.json`: carry out the model's verdicts with every guard re-checked at the moment of acting.

PLAN.json: {"learn": false, "items": [{"repo": "github:owner/name", "pr": 9, "head_sha": "<the SHA the model judged>",
"verdict": "merge|close|escalate|hold|fix|skip", "read_whole_diff": false, "rule": "issue-first",
"confirmed_by_reading": false, "method": null, "note": "private, digest only"}]}

The model can move any PR toward escalate; merge and close happen only where the table, re-run now, allows them."""

from __future__ import annotations

from . import prs as P
from . import scope as S
from . import verdict as V
from .providers.base import as_dict
from .providers.registry import get_provider, parse_repo_arg
from .util import EverkeepError, iso, now

VERDICTS = ("merge", "close", "escalate", "hold", "fix", "skip")


def draft_plan(facts_list: list[dict], learn: bool) -> dict:
    """A plan with the table's verdict for each PR, for the model to read, change toward escalate, and confirm."""
    items = []
    for f in facts_list:
        c = f["classification"]
        cls = c["class"]
        human = not f.get("bot") and not c.get("docs_only")
        verdict = {"own": "skip", "hold": "hold", "fix": "fix", "escalate": "escalate",
                   "merge-candidate": "merge", "close-candidate": "close" if c.get("superseded_by") else "escalate"}[cls]
        item = {"repo": f["repo"], "pr": f["number"], "head_sha": f["head_sha"], "verdict": verdict, "table": cls,
                "url": f["url"]}
        if verdict == "merge" and human:
            item["read_whole_diff"] = False  # the model sets true after reading every line
        if cls == "close-candidate" and not c.get("superseded_by"):
            item["note"] = "recommend close: read the whole diff; set verdict close, rule and confirmed_by_reading to close"
        items.append(item)
    return {"learn": learn, "created": iso(now()), "items": items}


class Caps:
    def __init__(self, cfg: dict):
        c = cfg.get("caps") or {}
        self.per_repo = int(c.get("merges_per_repo", 3))
        self.per_run = int(c.get("merges_per_run", 10))
        self.closes = int(c.get("closes_per_run", 5))
        self.merged: dict[str, int] = {}
        self.closed = 0

    def can_merge(self, repo: str) -> str | None:
        if sum(self.merged.values()) >= self.per_run:
            return f"cap of {self.per_run} merges per run reached"
        if self.merged.get(repo, 0) >= self.per_repo:
            return f"cap of {self.per_repo} merges per repo reached"
        return None


def refuse_reason(item: dict, facts: dict, fresh_checks: str | None, caps: Caps) -> str | None:
    """Why the table, re-run now, forbids this verdict; None when it allows it."""
    v = item["verdict"]
    c = facts["classification"]
    if facts["head_sha"] != item.get("head_sha"):
        return f"head moved from {str(item.get('head_sha'))[:12]} to {facts['head_sha'][:12]} after review; judge it again"
    if v == "merge":
        if c["class"] != "merge-candidate":
            return f"the table now says {c['class']}: " + "; ".join(c["reasons"][:3])
        if not facts.get("bot") and not c.get("docs_only") and not item.get("read_whole_diff"):
            return "human PR: merge only after the model has read the whole diff (read_whole_diff)"
        if facts.get("is_draft"):
            return "draft"
        if fresh_checks != "passed":
            return f"checks on {facts['head_sha'][:12]} are {fresh_checks}, not passed"
        return caps.can_merge(facts["repo"])
    if v == "close":
        if c["class"] != "close-candidate":
            return f"the table now says {c['class']}; escalate with 'recommend close' instead"
        if not c.get("superseded_by"):
            if not item.get("confirmed_by_reading"):
                return "human PR: close only after the model read the whole diff and found a content signal (confirmed_by_reading)"
            if item.get("rule") not in V.RULES:
                return f"close needs a rule from {', '.join(V.RULES)}"
        if caps.closed >= caps.closes:
            return f"cap of {caps.closes} closes per run reached"
    return None


def execute(plan: dict, store, apply: bool, learn: bool | None = None, run: dict | None = None) -> list[dict]:
    cfg = store.config()
    learn = bool(cfg.get("learn")) if learn is None else learn
    learn = learn or bool(plan.get("learn"))
    caps = Caps(cfg)
    results = []
    for item in plan.get("items", []):
        v = item.get("verdict")
        res = {"repo": item.get("repo"), "pr": item.get("pr"), "verdict": v, "learn": learn, "apply": apply,
               "actions": [], "refused": None}
        results.append(res)
        if v not in VERDICTS:
            res["refused"] = f"unknown verdict {v!r}"
            continue
        if v == "skip":
            continue
        try:
            rid = parse_repo_arg(str(item["repo"]), hosts=cfg.get("hosts"))
            provider = get_provider(rid, cfg)
            entry = S.describe(provider.get_repo(rid), store)
            facts = P.gather_pr(entry, int(item["pr"]), cfg, provider)
        except EverkeepError as e:
            res["refused"] = f"could not re-check: {e}"
            continue
        res["table"] = facts["classification"]["class"]
        res["url"] = facts["url"]
        res["title"] = P.title_cell(facts["title"])
        fresh = provider.checks_state(rid, facts["head_sha"]).state if v == "merge" else None
        why = refuse_reason(item, facts, fresh, caps)
        if why:
            res["refused"] = why
            continue
        n = facts["number"]
        actions = []
        state = store.repo_state(facts["repo"])
        posted_before = any(d.get("pr") == n and d.get("verdict_posted") for d in state.get("decisions", []))
        if learn or v in ("hold", "fix", "escalate"):
            body = res["comment"] = V.verdict_body(facts, v, learn)
            actions.append(provider.upsert_marked_comment(rid, n, V.MARKER, body, apply))
        if not learn:
            if v == "escalate":
                to_user = cfg.get("escalate_to") or provider.whoami()
                actions += provider.escalate(rid, n, to_user, facts["author"].lower() != to_user.lower(), apply)
            elif v == "merge":
                method = item.get("method") or provider.usual_merge_method(rid)
                a = provider.merge(rid, n, method, facts["head_sha"], apply)
                actions.append(a)
                if a.ok:
                    caps.merged[facts["repo"]] = caps.merged.get(facts["repo"], 0) + 1
                    if posted_before:
                        res["comment"] = V.verdict_body(facts, "merge", False)
                        actions.append(provider.upsert_marked_comment(rid, n, V.MARKER, res["comment"], apply))
            elif v == "close":
                res["comment"] = V.close_body(facts, item.get("rule"), False)  # public text: previewed like the rest
                actions += provider.close(rid, n, res["comment"], apply)
                caps.closed += 1
        res["actions"] = [as_dict(a) for a in actions]
        if apply:
            store.record_decision(facts["repo"], {
                "pr": n, "head_sha": facts["head_sha"], "verdict": v, "table": res["table"], "learn": learn,
                "verdict_posted": posted_before or any(a.kind == "verdict" and a.applied for a in actions),
                "ok": all(a.ok for a in actions), "run": (run or {}).get("id")})
    return results
