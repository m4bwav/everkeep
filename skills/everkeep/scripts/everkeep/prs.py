"""The PR duty's mechanical half: gather every fact the decision rules need for each open PR, then pre-classify."""

from __future__ import annotations

import json

from . import classify as C
from . import lockdiff, registries
from .providers.base import as_dict
from .providers.registry import get_provider
from .util import EverkeepError, age_days, clean_untrusted, fence_untrusted, parse_time


def _scripts(raw: bytes | None) -> dict | None:
    try:
        return (json.loads(raw or b"{}") or {}).get("scripts") or {}
    except ValueError:
        return None


def release_rows(bot: dict, provider) -> list[dict]:
    rows = []
    eco = bot.get("ecosystem", "")
    for u in bot.get("updates", []):
        new = registries.release_facts(eco, u["package"], u["to"], provider)
        row = {**u, "ecosystem": eco, "published": new.get("published"), "publisher": new.get("publisher"),
               "exists": new.get("exists"), "error": new.get("error")}
        row["age_days"] = age_days(parse_time(row["published"]))
        if eco == "npm" and u.get("from") and not new.get("error"):
            old = registries.release_facts(eco, u["package"], u["from"], provider)
            if not old.get("error"):
                row["prev_publisher"] = old.get("publisher")
                changed = bool(old.get("publisher") and new.get("publisher") and old["publisher"] != new["publisher"])
                downgraded = bool(old.get("trusted_publisher") and not new.get("trusted_publisher"))
                row["publisher_changed"] = changed or downgraded
                row["new_install_script"] = bool(new.get("has_install_script") and not old.get("has_install_script"))
        rows.append(row)
    return rows


def gather_pr(entry: dict, number: int, cfg: dict, provider=None) -> dict:
    repo = entry["repo"]
    provider = provider or get_provider(repo.id, cfg)
    d = provider.pr_detail(repo.id, number)
    pr = d.pr
    diff = provider.pr_diff(repo.id, number)
    files = [as_dict(x) for x in d.files]
    paths = [x["path"] for x in files]
    bot = C.parse_bot(pr.author, pr.head_ref, pr.title, d.body, paths) if pr.author_kind == "bot" else None
    facts = {
        "repo": entry["id"], "tier": entry["tier"], "visibility": entry.get("visibility"), "number": pr.number,
        "url": pr.url, "title": pr.title, "author": pr.author, "author_kind": pr.author_kind,
        "author_association": d.author_association, "is_draft": pr.is_draft, "head_sha": pr.head_sha,
        "head_ref": pr.head_ref, "base": pr.base, "labels": pr.labels, "created_at": pr.created_at,
        "checks": {"state": d.checks.state, "summary": d.checks.summary(), "checks": as_dict(d.checks.checks)},
        "files": files, "linked_issues": d.linked_issues, "additions": d.additions, "deletions": d.deletions,
        "bot": bot, "security": C.is_security(pr.labels, d.body),
    }
    ld = lockdiff.analyse(diff)
    facts["lockdiff"] = ld.to_dict()
    facts["unexpected"] = ld.unexpected
    if any(p.startswith(".github/workflows/") for p in paths):
        facts["pin_only"] = C.workflow_pin_only(lockdiff.split_diff(diff))
    for p in paths:
        if p.endswith("package.json"):
            before, after = _scripts(provider.file(repo.id, p, pr.base)), _scripts(provider.file(repo.id, p, pr.head_sha))
            if before is None or after is None or before != after:
                facts["package_json_scripts_changed"] = True
    if bot:
        facts["releases"] = release_rows(bot, provider)
        bad = {c.lower() for c in cfg.get("compromised") or []}
        facts["compromised"] = [f"{u['package']}@{u['to']}" for u in bot["updates"]
                                if f"{u['package']}@{u['to']}".lower() in bad]
        if facts["compromised"]:
            facts["unexpected"] = facts["unexpected"] + [f"known-compromised {c}" for c in facts["compromised"]]
    elif pr.author_kind in ("outside", "member"):
        try:
            facts["author_history"] = as_dict(provider.author_history(repo.id, pr.author))
        except EverkeepError as e:
            facts["author_history"] = {"error": str(e)[:200]}
    facts["classification"] = C.classify(facts, cfg)
    return facts


def gather_repo(entry: dict, cfg: dict) -> list[dict]:
    provider = get_provider(entry["repo"].id, cfg)
    out = [gather_pr(entry, pr.number, cfg, provider) for pr in provider.list_open_prs(entry["repo"].id)]
    for old, new in C.superseded(out).items():
        f = next(x for x in out if x["number"] == old)
        if f["classification"]["class"] != "own":
            f["classification"] = {"class": "close-candidate", "superseded_by": new, "hold_until": None,
                                   "reasons": [f"superseded by #{new}, which updates the same dependency"]}
    return out


def show(facts: dict, diff: str, body: str) -> str:
    """One PR's facts for the model to read, untrusted text fenced."""
    c = facts["classification"]
    lines = [f"# {facts['repo']}#{facts['number']} ({c['class']})", "", f"URL: {facts['url']}",
             f"Author: {facts['author']} ({facts['author_kind']}, {facts['author_association']})",
             f"Head: {facts['head_sha']}  Checks: {facts['checks']['summary']}",
             f"Files: {len(facts['files'])} (+{facts['additions']} -{facts['deletions']})", "",
             "Reasons:", *[f"- {r}" for r in c["reasons"]], ""]
    if c.get("after_fix"):
        lines += [f"Known fix: {c['fix_recipe']} (references/prs.md)" if c.get("fix_recipe") else "Known fix: none; diagnose from the log",
                  f"After the fix: {c['after_fix']}: " + "; ".join(c.get("after_fix_reasons") or []), ""]
    if facts.get("releases"):
        lines += ["Releases:"] + [f"- {r['package']} {r['from']} -> {r['to']} ({r['bump']}): published {r.get('published')}, "
                                  f"publisher {r.get('publisher')}" + (f" (was {r['prev_publisher']})" if r.get('prev_publisher') else "")
                                  + (f", error {r['error']}" if r.get("error") else "") for r in facts["releases"]] + [""]
    lines += [fence_untrusted("PR title", facts["title"], 300), "", fence_untrusted("PR body", body, 15000), "",
              fence_untrusted("diff", diff, 60000)]
    return "\n".join(lines)


def title_cell(title: str) -> str:
    t = clean_untrusted(title, 90).replace("`", "'").replace("\n", " ")
    return t[:90]
