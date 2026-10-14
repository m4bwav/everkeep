"""keep.py's commands. Every command takes the same scope arguments, prints the resolved scope first, writes JSON
with --json and Markdown otherwise, and is a dry run unless --apply. Only `act` writes to a host."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import VERSION
from . import act as A
from . import duties as D
from . import gaps as G
from . import prs as P
from . import report as REP
from . import runs as RUNS
from . import scope as S
from .providers.base import AuthMissing, as_dict
from .providers.registry import BUILT, get_provider
from .state import Store
from .util import EverkeepError, collapse_reasons, dumps, md_table, now, read_json, write_json


def _out(args, data, markdown: str) -> None:
    print(dumps(data) if getattr(args, "json", False) else markdown)


def _scope_md(entries: list[dict]) -> str:
    return md_table(S.ENTRY_HEADERS, [S.entry_row(e) for e in entries])


def _entries_json(entries: list[dict]) -> list[dict]:
    return [{k: (v.to_dict() if hasattr(v, "to_dict") else v) for k, v in e.items()} for e in entries]


# ------------------------------------------------------------------ commands

def cmd_providers(args, store):
    cfg = store.config()
    rows, data = [], []
    for name in sorted(BUILT):
        try:
            p = get_provider(name, cfg)
            who, login = p.whoami(), ""
        except AuthMissing as e:
            who, login = None, e.login_command
        caps = get_provider(name, cfg).capabilities() if who else None
        data.append({"provider": name, "account": who, "login_command": login, "capabilities": as_dict(caps) if caps else None,
                     "extra_accounts": (cfg.get("accounts") or {}).get(name, [])})
        rows.append([name, who or "not logged in", login or "", ", ".join(k for k, v in as_dict(caps).items() if v is True) if caps else ""])
    md = md_table(["provider", "account", "login command", "capabilities"], rows)
    md += "\n\nNot built yet: gitlab, codeberg/forgejo/gitea, bitbucket, azure (references/providers.md)."
    overlay = store.overlay_dir
    md += f"\nState: {store.root}. Overlay: {overlay} ({'present' if (overlay / 'OVERLAY.md').exists() or (overlay / 'overlay.json').exists() else 'none'})."
    _out(args, data, md)


def cmd_scope(args, store):
    if args.action == "list":
        sels = store.selections()
        _out(args, sels, md_table(["selection", "spec"], [[k, json.dumps(v)] for k, v in sorted(sels.items())]) if sels else "No saved selections.")
        return
    entries = S.resolve(args, store)
    if args.action == "save":
        spec = {"repos": [e["id"] for e in entries]} if args.frozen else \
            {k: v for k, v in {"filter": args.filter, "all": args.all or None, "repos": args.repo or None,
                               "include": {k: True for k in ("forks", "archived", "private") if getattr(args, f"include_{k}")} or None,
                               "duties": args.duties.split(",") if args.duties else None}.items() if v}
        path = store.save_selection(args.name, spec)
        _out(args, {"saved": args.name, "spec": spec, "resolves_to": [e["id"] for e in entries]},
             f"Saved selection {args.name} to {path}: {json.dumps(spec)}\n\n{_scope_md(entries)}")
        return
    _out(args, _entries_json(entries), f"{len(entries)} repo(s), in run order:\n\n{_scope_md(entries)}")


def cmd_inventory(args, store):
    entries = S.resolve(args, store)
    reg = D.vault_registry(store.config())
    rows, data = [], []
    for e in entries:
        k = D.kb(e, store, reg)
        rows.append(S.entry_row(e) + [e["tier_reason"], "yes" if k["ai_docs"] else "no",
                                      {True: "yes", False: "no", None: "?"}[k["registered"]]])
        data.append({**_entries_json([e])[0], "kb": k})
    _out(args, data, md_table(S.ENTRY_HEADERS + ["why this tier", "ai-docs", "in vault"], rows))


def cmd_prs(args, store):
    cfg = store.config()
    if args.action == "show":
        repo_text, _, n = args.target.rpartition("#")
        rid = S.repo_id(repo_text, cfg) if repo_text else S.current_repo(".", cfg.get("hosts"))
        p = get_provider(rid, cfg)
        entry = S.describe(p.get_repo(rid), store)
        facts = P.gather_pr(entry, int(n), cfg, p)
        if args.json:
            print(dumps(facts))
        else:
            print(P.show(facts, p.pr_diff(rid, int(n)), p.pr_detail(rid, int(n)).body))
        return
    entries = S.resolve(args, store)
    all_facts = []
    for e in entries:
        all_facts += P.gather_repo(e, cfg)
    if args.plan:
        plan = A.draft_plan(all_facts, bool(args.learn or cfg.get("learn")))
        write_json(Path(args.plan), plan)
    rows = [[f"{f['repo'].split(':', 1)[-1]}#{f['number']}", f["classification"]["class"], f["checks"]["state"],
             P.title_cell(f["title"]), "; ".join(collapse_reasons(f["classification"]["reasons"])[:3])] for f in all_facts]
    md = _scope_md(entries) + "\n\n" + (md_table(["PR", "class", "checks", "title (untrusted)", "why"], rows) if rows else "No open PRs.")
    if args.plan:
        md += f"\n\nDraft plan written to {args.plan}: read it, move items toward escalate as you judge, then `keep.py act {args.plan}`."
    _out(args, {"scope": _entries_json(entries), "prs": all_facts}, md)


def _per_repo(args, store, fn, render):
    entries = S.resolve(args, store)
    results = [fn(e) for e in entries]
    _out(args, results, _scope_md(entries) + "\n\n" + "\n\n".join(render(r) for r in results))


def cmd_gaps(args, store):
    def render(g):
        if g.get("error"):
            return f"## {g['repo']}\n\nnot checked: {g['error']}"
        md = f"## {g['repo']}\n\n" + md_table(["gap", "status", "detail", "fix"], [[x["gap"], x["status"], x["detail"], x["fix"]] for x in g["gaps"]])
        if g["deadlines"]:
            md += "\n\nDeadlines:\n" + "\n".join(f"- {d['date']}: {d['what']} ({d['where']})" for d in g["deadlines"])
        if g["not_checked"]:
            md += "\n\nNot checked:\n" + "\n".join(f"- {x}" for x in g["not_checked"])
        return md
    _per_repo(args, store, lambda e: G.audit(e, store, args.deep), render)


def cmd_vulns(args, store):
    def render(v):
        lines = [f"## {v['repo']}", ""]
        for kind, items in v["alerts"].items():
            lines.append(f"- {kind} alerts: {len(items)}" + "".join(f"\n  - {a['severity']} {a['package']}" + (f" ({a['scope']})" if a.get("scope") else "")
                                                                    + f" {a['summary'][:80]} {a['url']}" for a in items[:10]))
        lines += [f"- {s['tool']}: {s['status']}, {s.get('findings', '?')} finding(s) {s.get('detail', '')}" for s in v["scanners"]]
        lines += [f"- not checked: {x}" for x in v["not_checked"]]
        return "\n".join(lines)
    _per_repo(args, store, lambda e: D.vulns(e, store, args.clone), render)


def cmd_deps(args, store):
    def render(d):
        md = f"## {d['repo']}\n\n{d['checked']} direct dependencies checked.\n\n"
        if d["outdated"]:
            md += md_table(["ecosystem", "package", "current", "latest", "bump", "published"],
                           [[o["ecosystem"], o["package"], o["current"], o["latest"], o["bump"], str(o.get("latest_published"))[:10]] for o in d["outdated"]])
        if d.get("held"):
            md += "\n\nHeld by the repo's own choice (not bump candidates):\n" + "\n".join(f"- {h}" for h in d["held"])
        if d["toolchains"]:
            md += "\n\nToolchains:\n" + "\n".join(f"- {t['tool']}: {t['value']} (floor {t['floor']})" for t in d["toolchains"])
        if d["errors"]:
            md += "\n\nNot checked:\n" + "\n".join(f"- {x}" for x in d["errors"][:10])
        return md
    _per_repo(args, store, lambda e: D.deps(e, store), render)


def cmd_kb(args, store):
    reg = D.vault_registry(store.config())
    _per_repo(args, store, lambda e: D.kb(e, store, reg),
              lambda k: f"- {k['repo']}: {k['status']} (ai-docs {k['ai_docs']}, registered {k['registered']})"
                        + "".join(f"\n  - `{c}`" for c in k["commands"]) + "".join(f"\n  - not checked: {x}" for x in k["not_checked"]))


def cmd_research(args, store):
    _per_repo(args, store, lambda e: D.research(e, store), lambda r: "```json\n" + dumps(r) + "\n```")


def cmd_act(args, store):
    plan = read_json(Path(args.plan))
    if plan is None:
        raise EverkeepError(f"no plan at {args.plan}")
    results = A.execute(plan, store, apply=args.apply, learn=True if args.learn else None)
    if args.run:
        run = store.load_run(args.run)
        write_json(store.run_dir(run["id"]) / f"act-{now().strftime('%H%M%S')}.json", results)
    rows = []
    for r in results:
        acts = "; ".join(f"{'did' if a['applied'] else 'would'} {a['kind']}: {a['detail']}" + ("" if a["ok"] else f" FAILED {a['error']}")
                         for a in r["actions"]) or ""
        rows.append([f"{r['repo']}#{r['pr']}", r["verdict"], r.get("table", ""), r["refused"] or acts])
    head = ("APPLIED" if args.apply else "DRY RUN (add --apply to act)") + (", learning mode" if any(r["learn"] for r in results) else "")
    tail = ""
    previews = [f"## {r['repo']}#{r['pr']}\n\n{r['comment']}" for r in results if r.get("comment")]
    if previews and not args.apply:
        out = Path(args.plan).with_suffix(".comments.md")
        out.write_text("\n\n".join(previews) + "\n", encoding="utf-8")
        tail = f"\n\nThe comments it would post, word for word: {out}. Read them before --apply."
    _out(args, results, f"{head}\n\n" + md_table(["PR", "verdict", "table now", "result"], rows) + tail)


D11_SWITCH_ON = ("dependency_alerts", "security_updates", "secret_scanning", "push_protection",
                 "private_vuln_reporting", "code_scanning_default", "pr_creation_cap")


def cmd_enable(args, store):
    """Switch on the settings decision D11 allows without asking; only those, and only switching on."""
    features = list(D11_SWITCH_ON) if args.features == "all" else [f.strip() for f in args.features.split(",") if f.strip()]
    bad = [f for f in features if f not in D11_SWITCH_ON]
    if bad:
        raise EverkeepError(f"not allowed without asking: {', '.join(bad)}; allowed: {', '.join(D11_SWITCH_ON)}")
    entries = S.resolve(args, store)
    rows, data = [], []
    for e in entries:
        p = get_provider(e["repo"].id, store.config())
        settings = p.repo_settings(e["repo"].id)
        for f in features:
            if f in ("code_scanning_default", "pr_creation_cap") and e["visibility"] != "public":
                rows.append([e["id"], f, "skipped: public repos only"])
                continue
            cur = settings.get(f)
            if cur is True or cur == "configured" or (isinstance(cur, dict) and cur.get("enabled")):
                rows.append([e["id"], f, "already on"])
                continue
            a = p.enable(e["repo"].id, f, args.apply)
            data.append(as_dict(a))
            rows.append([e["id"], f, ("did" if a.applied else "would") + f" switch on{'' if a.ok else ' FAILED ' + a.error[:120]}"])
    _out(args, data, ("APPLIED" if args.apply else "DRY RUN (add --apply)") + "\n\n" + md_table(["repo", "setting", "result"], rows))


def cmd_run(args, store):
    if args.action == "start":
        entries = S.resolve(args, store)
        duties = args.duties.split(",") if args.duties else None
        if duties is None and args.select:
            duties = (store.selections().get(args.select) or {}).get("duties")
        duties = duties or list(store.config().get("duties") or ["prs", "vulns", "gaps", "kb"])
        bad = [d for d in duties if d not in RUNS.ALL_DUTIES]
        if bad:
            raise EverkeepError(f"unknown duties {bad}; known: {', '.join(RUNS.ALL_DUTIES)}")
        run = store.new_run(entries, duties, S.scope_spec(args), bool(args.learn or store.config().get("learn")), False)
        print(f"Run {run['id']}: {len(entries)} repo(s), duties {', '.join(duties)}. Target list frozen.\n\n{_scope_md(entries)}\n")
    elif args.action == "resume":
        run = RUNS.resume(store.load_run(args.run_id), store, args.failed, args.release_held)
    else:
        run = store.load_run(args.run_id or "latest")
        rows = [[r["id"], r["tier"], r["status"], r["reason"]] for r in run["repos"]]
        _out(args, run, f"Run {run['id']}: " + ", ".join(f"{n} {s}" for s, n in sorted(RUNS.summary(run).items())) +
             (f"\n\nSTOPPED WIDENING at {run['stopped']['repo']}: {run['stopped']['finding']}" if run.get("stopped") else "")
             + "\n\n" + md_table(["repo", "tier", "status", "reason"], rows))
        return
    try:
        RUNS.process(run, store, args.max, args.deep, args.clone, echo=lambda m: print(m, file=sys.stderr))
    except KeyboardInterrupt:
        print(f"\nInterrupted. Nothing lost but the repo in flight. Resume with: keep.py run resume {run['id']}", file=sys.stderr)
        raise SystemExit(130)
    nxt = RUNS.first_pending(run)
    print(f"Run {run['id']}: " + ", ".join(f"{n} {s}" for s, n in sorted(RUNS.summary(run).items())) +
          (f". Next pending: {nxt}; continue with `keep.py run resume {run['id']}`." if nxt else ". All repos processed; `keep.py report " + run["id"] + "` writes the digest."))


def cmd_report(args, store):
    run = store.load_run(args.run_id)
    cfg = store.config()
    reviewer = cfg.get("escalate_to")
    if not reviewer:
        try:
            reviewer = get_provider("github", cfg).whoami()
        except EverkeepError:
            reviewer = None
    text = REP.build(run, store, reviewer)
    _out(args, {"run": run["id"], "digest": str(store.run_dir(run["id"]) / "digest.md"), "text": text}, text)


def cmd_state(args, store):
    cfg = store.config()
    rid = str(S.repo_id(args.repo, cfg))
    if args.action == "forget":
        print(f"forgot {rid}" if store.forget(rid) else f"nothing stored for {rid}")
        return
    st = store.repo_state(rid)
    print(dumps(st))


# ------------------------------------------------------------------ parser

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="keep.py", description="everkeep: keep repositories healthy (dry run unless --apply).")
    ap.add_argument("--version", action="version", version=f"everkeep {VERSION}")
    sub = ap.add_subparsers(dest="command", required=True)

    def add(name, fn, scope=True, help=""):
        p = sub.add_parser(name, help=help)
        p.add_argument("--json", action="store_true", help="JSON instead of Markdown")
        if scope:
            S.add_scope_args(p)
        p.set_defaults(fn=fn)
        return p

    add("providers", cmd_providers, scope=False, help="configured providers, account, auth and capabilities")
    p = add("scope", cmd_scope, help="resolve, save or list scopes")
    p.add_argument("action", choices=["resolve", "save", "list"])
    p.add_argument("name", nargs="?", help="selection name (save)")
    p.add_argument("--frozen", action="store_true", help="save the resolved list instead of the filter")
    p.add_argument("--duties", help="duties a run of this selection does, comma-separated")
    add("inventory", cmd_inventory, help="every repo in scope: tier, ecosystems, packages, clone, knowledge base")
    p = add("prs", cmd_prs, help="open PRs with facts and a pre-classification; `prs show REPO#N` for one")
    p.add_argument("action", nargs="?", choices=["list", "show"], default="list")
    p.add_argument("target", nargs="?", help="REPO#N (show)")
    p.add_argument("--plan", metavar="FILE", help="also write a draft PLAN.json for act")
    p.add_argument("--learn", action="store_true", help="mark the draft plan as learning mode")
    p = add("gaps", cmd_gaps, help="the modernization gap table and dated deadlines")
    p.add_argument("--deep", action="store_true", help="also run package-modernize's topics.py and lint-workflows.sh")
    p = add("vulns", cmd_vulns, help="provider alerts plus osv-scanner, npm audit, dotnet on a clone")
    p.add_argument("--clone", action="store_true", help="make a throwaway shallow clone when no local clone is known")
    add("deps", cmd_deps, help="outdated direct dependencies and toolchains")
    add("kb", cmd_kb, help="repos without an ai-docs knowledge base or vault registration")
    p = add("research", cmd_research, help="facts for an ecosystem note (ecosyste.ms, HN Algolia)")
    p.add_argument("action", choices=["gather"])
    p = add("act", cmd_act, scope=False, help="carry out a PLAN.json with guards re-checked now (dry run unless --apply)")
    p.add_argument("plan")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--learn", action="store_true", help="verdict comments only, whatever the plan says")
    p.add_argument("--run", metavar="RUN_ID", help="record the results in this run's digest")
    p = add("enable", cmd_enable, help="switch on the security settings decision D11 allows (dry run unless --apply)")
    p.add_argument("features", help="comma-separated, or all: " + ", ".join(D11_SWITCH_ON))
    p.add_argument("--apply", action="store_true")
    p = add("run", cmd_run, help="start, resume or show a resumable multi-repo run")
    p.add_argument("action", choices=["start", "resume", "status"])
    p.add_argument("run_id", nargs="?")
    p.add_argument("--duties", help=f"comma-separated, from {', '.join(RUNS.ALL_DUTIES)}")
    p.add_argument("--max", type=int, help="process at most N repos in this call")
    p.add_argument("--learn", action="store_true")
    p.add_argument("--deep", action="store_true")
    p.add_argument("--clone", action="store_true")
    p.add_argument("--failed", action="store_true", help="resume: retry the failed repos")
    p.add_argument("--release-held", action="store_true", help="resume: carry on after a stop the maintainer has seen")
    p = add("report", cmd_report, scope=False, help="the digest for a run")
    p.add_argument("run_id", nargs="?", default="latest")
    p = add("state", cmd_state, scope=False, help="per-repo memory")
    p.add_argument("action", choices=["show", "forget"])
    p.add_argument("repo")
    return ap


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", newline="\n")
        except (AttributeError, ValueError):
            pass
    args = build_parser().parse_args(argv)
    if args.command == "run" and args.action in ("resume",) and not args.run_id:
        print("keep.py: run resume needs a RUN_ID (keep.py run status shows the latest)", file=sys.stderr)
        return 2
    store = Store()
    try:
        args.fn(args, store)
    except EverkeepError as e:
        print(f"keep.py: {e}", file=sys.stderr)
        return e.exit_code
    return 0
