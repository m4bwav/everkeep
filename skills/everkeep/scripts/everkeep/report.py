"""The digest (design section 10): one per run, grouped by provider, saved to runs/<id>/digest.md and printed.
A dry run's digest has the same sections in the conditional ("Would merge")."""

from __future__ import annotations

from .prs import title_cell
from .runs import summary
from .util import atomic_write, read_json

SECTIONS = [("merge", "Merged", "Would merge"), ("close", "Closed", "Would close"),
            ("bump", "Outdated dependencies (bump candidates)", "Outdated dependencies (bump candidates)"), ("fix", "Fixed", "Needs a fix (bot PRs whose checks failed or did not run)"),
            ("escalate", "Waiting for the maintainer", "Would wait for the maintainer"),
            ("hold", "Held", "Held"), ("own", "Left alone (opened by the account everkeep runs as)", "Left alone (opened by the account everkeep runs as)")]
CLASS_TO_SECTION = {"merge-candidate": "merge", "close-candidate": "close", "fix": "fix", "escalate": "escalate",
                    "hold": "hold", "own": "own"}


def _names(repos: list[str], cap: int = 12) -> str:
    names = sorted(dict.fromkeys(repos))
    return ", ".join(names[:cap]) + (f" and {len(names) - cap} more" if len(names) > cap else "")


def _act_results(store, run: dict) -> dict[tuple, dict]:
    out = {}
    for p in sorted(store.run_dir(run["id"]).glob("act-*.json")):
        for res in read_json(p, []) or []:
            out[(res.get("repo"), res.get("pr"))] = res
    return out


def build(run: dict, store, reviewer: str | None = None) -> str:
    acts = _act_results(store, run)
    applied = any(r.get("apply") for r in acts.values())
    learn = run.get("learn") or any(r.get("learn") for r in acts.values())
    buckets: dict[str, list[str]] = {k: [] for k, _, _ in SECTIONS}
    refused, kb_lines, vuln_lines, deadlines, failed = [], [], [], {}, []
    not_checked: dict[str, list[str]] = {}  # message -> repos, so 60 repos missing one tool make one line
    gaps_by: dict[str, list[str]] = {}

    def nc(repo: str, items) -> None:
        for x in items:
            not_checked.setdefault(x, []).append(repo.split(":", 1)[-1])
    for r in run["repos"]:
        if r["status"] in ("failed", "skipped"):
            failed.append(f"- {r['id']}: {r['status']}: {r['reason']}")
        facts = store.load_facts(run, r["id"])
        if not facts:
            continue
        d = facts.get("duties", {})
        for f in d.get("prs", []):
            c = f["classification"]
            res = acts.get((f["repo"], f["number"]))
            sec = CLASS_TO_SECTION[c["class"]]
            line = f"- [{f['repo'].split(':', 1)[-1]}#{f['number']}]({f['url']}) {title_cell(f['title'])}: {'; '.join(c['reasons'][:3])}"
            if c.get("hold_until"):
                line += f" (until {c['hold_until'][:10]})"
            if res:
                if res.get("refused"):
                    refused.append(f"- {f['repo']}#{f['number']}: {res['refused']}")
                    continue
                sec = {"merge": "merge", "close": "close", "escalate": "escalate", "hold": "hold", "fix": "fix"}.get(res["verdict"], sec)
                if res.get("apply") and not res.get("learn") and not all(a.get("ok") for a in res.get("actions", [])):
                    line += " (an action failed: " + "; ".join(a.get("error", "") for a in res["actions"] if not a.get("ok")) + ")"
            buckets[sec].append(line)
        v = d.get("vulns")
        if v:
            nc(facts["repo"], v.get("not_checked", []))
            n = {k: len(x) for k, x in (v.get("alerts") or {}).items() if x}
            scans = [f"{s['tool']} {s.get('findings', '?')}" + (f" ({s['detail']})" if s.get("detail") else "")
                     for s in v.get("scanners", []) if s.get("findings")]
            if n or scans:
                vuln_lines.append(f"- {facts['repo']}: " + ", ".join([f"{c} {k} alerts" for k, c in n.items()] + scans))
        g = d.get("gaps")
        if g:
            nc(facts["repo"], g.get("not_checked", []))
            for x in g.get("gaps", []):
                if x["status"] == "gap":
                    gaps_by.setdefault(x["gap"], []).append(facts["repo"].split(":", 1)[-1])
            for dl in g.get("deadlines", []):
                deadlines.setdefault((dl["date"], dl["what"]), []).append(f"{facts['repo']} ({dl['where']})")
        k = d.get("kb")
        if k:
            nc(facts["repo"], k.get("not_checked", []))
            if k["status"] != "ok":
                kb_lines.append(f"- {facts['repo']}: {k['status']}" + (f": `{k['commands'][0]}`" if k.get("commands") else ""))
        dp = d.get("deps")
        if dp and dp.get("outdated"):
            buckets["bump"] += [f"- {facts['repo']}: {o['package']} {o['current']} -> {o['latest']} ({o['bump']}, "
                                f"published {str(o.get('latest_published'))[:10]})" for o in dp["outdated"][:8]]
    counts = summary(run)
    mode = "applied" if applied else "dry run"
    if learn:
        mode += ", learning mode (verdict comments only)"
    out = [f"# everkeep digest: run {run['id']}", "",
           f"Started {run['created']}. Mode: {mode}. Duties: {', '.join(run['duties'])}. "
           f"Repos: {len(run['repos'])} (" + ", ".join(f"{n} {s}" for s, n in sorted(counts.items())) + ")."]
    if run.get("stopped"):
        s = run["stopped"]
        out += ["", "## Stopped widening", "",
                f"At {s['repo']}: {s['finding']}. The remaining repos are held until the maintainer has looked; "
                f"`keep.py run resume {run['id']} --release-held` carries on."]
    if deadlines:
        out += ["", "## Deadlines", ""]
        for (date, what), where in sorted(deadlines.items()):
            out.append(f"- **{date}**: {what}. " + "; ".join(where[:6]) + (f" and {len(where) - 6} more" if len(where) > 6 else ""))
    out += ["", "## github"]
    for key, done_title, dry_title in SECTIONS:
        lines = buckets[key]
        if not lines:
            continue
        title = done_title if applied and not learn else dry_title
        out += ["", f"### {title}", ""] + lines
        if key == "escalate" and applied and not learn and reviewer:
            out += ["", f"On the review list: https://github.com/pulls?q=is%3Aopen+is%3Apr+assignee%3A{reviewer}+archived%3Afalse"]
    if refused:
        out += ["", "### Refused at the moment of acting", ""] + refused
    if vuln_lines:
        out += ["", "### Vulnerabilities", ""] + vuln_lines
    if gaps_by:
        out += ["", "### Modernization gaps (per gap, most repos first)", ""]
        out += [f"- {gap} ({len(repos)}): {_names(repos)}" for gap, repos in sorted(gaps_by.items(), key=lambda kv: -len(kv[1]))]
    if kb_lines:
        out += ["", "### Knowledge base", ""] + kb_lines
    if not_checked:
        out += ["", "### Not checked", ""]
        for msg, repos in sorted(not_checked.items(), key=lambda kv: -len(kv[1])):
            every = len(set(repos)) == len(run["repos"]) > 1
            out.append(f"- {msg} ({'every repo' if every else _names(repos)})")
    if failed:
        out += ["", "### Failed or skipped repos", ""] + failed
    pending = [r["id"] for r in run["repos"] if r["status"] == "pending"]
    if pending:
        out += ["", f"{len(pending)} repo(s) still pending: `keep.py run resume {run['id']}`."]
    text = "\n".join(out) + "\n"
    atomic_write(store.run_dir(run["id"]) / "digest.md", text)
    return text
