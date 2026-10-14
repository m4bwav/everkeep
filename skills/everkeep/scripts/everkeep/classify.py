"""Pre-classify a pull request from its gathered facts (design section 6). First matching row wins:

    own -> hold -> fix -> escalate -> close-candidate -> merge-candidate -> escalate (no rule matched)

The model may move a PR toward escalate freely and never toward merge against this table; `act` re-runs it at the
moment of acting and refuses a merge or close the table does not allow."""

from __future__ import annotations

import datetime as dt
import re

from .lockdiff import NEW_PACKAGES
from .util import age_days, day, iso, parse_time, safe_token

CLASSES = ("own", "hold", "fix", "escalate", "close-candidate", "merge-candidate")

EXECUTED = [r"^\.github/workflows/", r"^\.github/actions/", r"(^|/)action\.ya?ml$", r"(^|/)\.mcp\.json$",
            r"(^|/)\.claude/", r"(^|/)\.vscode/", r"(^|/)\.husky/", r"(^|/)\.npmrc$", r"(^|/)\.yarnrc",
            r"(^|/)AGENTS\.md$", r"(^|/)CLAUDE(\.local)?\.md$", r"(^|/)\.gemini/", r"(^|/)\.cursor/",
            r"(^|/)\.devcontainer/", r"^\.github/dependabot\.ya?ml$", r"(^|/)CODEOWNERS$", r"(^|/)renovate\.json5?$",
            r"(^|/)\.gitlab-ci\.yml$", r"(^|/)bitbucket-pipelines\.yml$", r"(^|/)azure-pipelines", r"^\.forgejo/",
            r"^\.gitea/", r"^\.woodpecker", r"(^|/)binding\.gyp$", r"(^|/)Dockerfile", r"(^|/)\.releaserc",
            r"(^|/)release\.config\.", r"(^|/)nuget\.config$", r"(^|/)copilot-instructions\.md$",
            r"(^|/)\.goreleaser", r"(^|/)Makefile$", r"(^|/)\.pre-commit-config\.yaml$"]
DOCS = [r"\.(md|markdown|txt|rst|adoc)$", r"^docs/", r"(^|/)LICENSE", r"^\.github/images/"]
FIRST_PARTY_ACTIONS = {"actions", "github"}
_PIN = re.compile(r"^\s*-?\s*uses:\s*([\w.-]+)/([\w.-]+)(/[^@\s]*)?@([0-9a-f]{40})\s*#\s*v?([\w.+-]+)\s*$")


def is_executed(path: str) -> bool:
    return any(re.search(p, path) for p in EXECUTED)


def is_docs(path: str) -> bool:
    return not is_executed(path) and any(re.search(p, path, re.I) for p in DOCS)


def _vparts(v: str) -> list[int]:
    out = []
    for p in re.split(r"[.+-]", (v or "").lstrip("vV")):
        if p.isdigit():
            out.append(int(p))
        else:
            break
    return out


def bump_kind(old: str, new: str) -> str:
    a, b = _vparts(old), _vparts(new)
    if not a or not b:
        return "unknown"
    a += [0] * (3 - len(a))
    b += [0] * (3 - len(b))
    if b[0] != a[0]:
        return "major"
    if a[0] == 0 and b[1] != a[1]:
        return "major"  # 0.x minor bumps break by semver convention
    if b[1] != a[1]:
        return "minor"
    return "patch"


# ------------------------------------------------------------------ bot PRs

_UPDATES = [re.compile(r"Updates? `([^`]+)` from ([\w.+-]+) to ([\w.+-]+)"),
            re.compile(r"(?:Bumps|Updated) \[([^\]]+)\]\([^)]*\) from ([\w.+-]+) to ([\w.+-]+)"),  # Updated: NuGet groups
            re.compile(r"[Bb]ump (\S+) from ([\w.+-]+) to ([\w.+-]+)")]


def parse_bot(author: str, head_ref: str, title: str, body: str, files: list[str]) -> dict | None:
    """Who the bot is, the ecosystem, and each update (package, from, to, bump) from Dependabot's or Renovate's text.
    The author is verified by the host; the text is still reduced to safe characters before any of it is reused."""
    login = author.lower()
    bot = "dependabot" if login.startswith("dependabot") else "renovate" if login.startswith("renovate") else None
    if bot is None:
        return None
    from .registries import ECOSYSTEMS
    eco = ""
    m = re.match(r"dependabot/([^/]+)/", head_ref or "")
    if m:
        eco = ECOSYSTEMS.get(m.group(1), m.group(1))
    elif any(f.startswith(".github/workflows/") for f in files):
        eco = "actions"
    elif any(f.endswith(("package.json", "package-lock.json")) for f in files):
        eco = "npm"
    elif any(f.endswith((".csproj", "packages.lock.json", "Directory.Packages.props")) for f in files):
        eco = "nuget"
    updates, seen = [], set()
    for rx in _UPDATES:
        for pkg, old, new in rx.findall((body or "") + "\n" + (title or "")):
            pkg, old, new = safe_token(pkg), old.rstrip("."), new.rstrip(".")  # "from 7.0.1 to 7.0.2."
            if pkg in seen or not pkg:
                continue
            seen.add(pkg)
            updates.append({"package": pkg, "from": safe_token(old, 40), "to": safe_token(new, 40),
                            "bump": bump_kind(old, new)})
    if bot == "renovate" and not updates:
        m = re.search(r"[Uu]pdate (?:dependency )?(\S+) to v?([\w.+-]+)", title or "")
        if m:
            updates.append({"package": safe_token(m.group(1)), "from": "", "to": safe_token(m.group(2), 40), "bump": "unknown"})
    if eco == "dotnet-sdk":
        for u in updates:
            u["package"] = "dotnet-sdk"
    return {"bot": bot, "ecosystem": eco, "updates": updates, "group": len(updates) > 1 or " group " in (title or "")}


def is_security(labels: list[str], body: str) -> bool:
    return any("security" in (l or "").lower() for l in labels) or bool(re.search(r"\bGHSA-[\w-]+|\bCVE-\d{4}-\d+", body or ""))


def workflow_pin_only(diff_files) -> dict:
    """D7: every changed workflow line is a `uses:` SHA pin of a first-party action (actions/*, github/*) moving by a
    patch or minor version, with the version comment."""
    pairs, problems = 0, []
    for fd in diff_files:
        if not fd.path.startswith(".github/workflows/"):
            continue
        rem = [l for l in fd.removed if l.strip()]
        add = [l for l in fd.added if l.strip()]
        if len(rem) != len(add):
            problems.append(f"{fd.path}: {len(rem)} lines removed, {len(add)} added")
            continue
        for old, new in zip(rem, add):
            mo, mn = _PIN.match(old), _PIN.match(new)
            if not (mo and mn):
                problems.append(f"{fd.path}: a changed line is not a SHA-pinned uses: line")
                break
            if mo.group(1, 2, 3) != mn.group(1, 2, 3):
                problems.append(f"{fd.path}: the action itself changed")
                break
            if mo.group(1) not in FIRST_PARTY_ACTIONS:
                problems.append(f"{fd.path}: {mo.group(1)}/{mo.group(2)} is not a first-party action")
                break
            kind = bump_kind(mo.group(5), mn.group(5))
            if kind not in ("patch", "minor"):
                problems.append(f"{fd.path}: {mo.group(1)}/{mo.group(2)} moves by a {kind} version")
                break
            pairs += 1
    return {"ok": pairs > 0 and not problems, "pins": pairs, "problems": problems}


# ------------------------------------------------------------------ the table

def _cooldown(update: dict, cfg: dict) -> int:
    c = cfg.get("cooldown") or {}
    return int(c.get("major_days", 7) if update.get("bump") == "major" else c.get("days", 3))


def classify(f: dict, cfg: dict | None = None) -> dict:
    cfg = cfg or {}
    reasons: list[str] = []
    files = [x["path"] for x in f.get("files", [])]
    checks = (f.get("checks") or {}).get("state", "none")
    bot = f.get("bot")
    kind = f.get("author_kind")
    tier = f.get("tier", "low")
    docs_only = bool(files) and all(is_docs(p) for p in files)
    security = f.get("security", False)
    out = {"class": None, "reasons": reasons, "hold_until": None, "docs_only": docs_only}

    def done(cls: str) -> dict:
        out["class"] = cls
        return out

    # own: the account everkeep runs as opened it (another session's work); left to its author
    if kind == "owner" and not bot:
        reasons.append("opened by the account everkeep runs as; left to its author")
        return done("own")

    # hold
    if f.get("is_draft"):
        reasons.append("draft")
        return done("hold")
    if checks == "pending":
        reasons.append("checks still running on " + (f.get("head_sha") or "")[:12])
        return done("hold")
    if bot and not security:
        until = None
        for r in f.get("releases", []):
            pub = parse_time(r.get("published"))
            if pub is None:
                continue
            days = _cooldown(r, cfg)
            ready = pub + dt.timedelta(days=days)
            if age_days(pub) is not None and age_days(pub) < days:
                reasons.append(f"{r['package']} {r['to']} was published {day(pub)}; the cooldown is {days} days")
                until = max(until, ready) if until else ready
        if until:
            out["hold_until"] = iso(until)
            return done("hold")

    # fix: a bot PR whose checks failed or did not run
    if bot and checks in ("failed", "not_run"):
        failing = [c["name"] for c in (f.get("checks") or {}).get("checks", []) if c["state"] in ("failed", "not_run")]
        if checks == "failed":
            reasons.append("checks failed: " + ", ".join(failing[:5]))
        else:
            reasons.append("checks did not run (cancelled or skipped): " + ", ".join(failing[:5]))
            if f.get("visibility") == "private":
                reasons.append("private repo: its self-hosted runner may be offline (the overlay's private_runner check)")
        lock = f.get("lockdiff") or {}
        reasons += lock.get("reasons", [])
        recipe = fix_recipe(f)
        if recipe:
            out["fix_recipe"] = recipe
            lock = {**lock, "reasons": [r for r in lock.get("reasons", []) if FIX_RECIPES[recipe]["repairs"] not in r]}
            lock["clean"] = not lock["reasons"]
        # What the table says once the fix lands and CI is green: the verdict comment says it up front, so a fix
        # that still ends with the maintainer (a new transitive package, say) is not a surprise later.
        after = classify({**f, "checks": {"state": "passed", "checks": []}, "lockdiff": lock}, cfg)
        out["after_fix"], out["after_fix_reasons"] = after["class"], after["reasons"]
        return done("fix")

    # escalate
    esc: list[str] = []
    if tier in ("high", "shared") and not docs_only:
        esc.append(f"repo tier {tier}: every change that is not docs-only goes to the maintainer")
    for u in (bot or {}).get("updates", []):
        if u["bump"] == "major":
            esc.append(f"major bump: {u['package']} {u['from']} to {u['to']}")
    executed = [p for p in files if is_executed(p)]
    pin = f.get("pin_only") or {}
    if executed:
        if bot and pin.get("ok") and all(p.startswith(".github/workflows/") for p in executed):
            reasons.append(f"workflow change is {pin['pins']} first-party action pin bump(s) only (rule D7)")
        else:
            esc.append("touches executed config: " + ", ".join(executed[:5]))
            esc += pin.get("problems", [])[:3]
    if f.get("package_json_scripts_changed"):
        esc.append("changes package.json scripts")
    deleted = [x["path"] for x in f.get("files", []) if x.get("status") == "deleted" and not is_docs(x["path"])]
    if deleted:
        esc.append("deletes files: " + ", ".join(deleted[:5]))
    lock = f.get("lockdiff") or {}
    new = [r for r in lock.get("reasons", []) if f": {NEW_PACKAGES} " in r]
    esc += [r for r in lock.get("reasons", []) if r not in new][:6]
    danger = [f"new package {t['package']}: {d}" for t in f.get("transitive", []) for d in t.get("danger", [])]
    if danger or (new and "transitive" not in f):  # D14: a new package escalates only with a danger signal
        esc += new[:3] + danger[:6]
    elif new:
        reasons += new[:3] + ["no danger signal in the new packages: known owners, not brand new, on the registry (rule D14)"]
    for r in f.get("releases", []):
        if r.get("error"):
            esc.append(f"could not verify when {r['package']} {r['to']} was published: {r['error'][:120]}")
        elif r.get("exists") is False:
            esc.append(f"{r['package']} {r['to']} not found on its registry")
        if r.get("publisher_changed"):
            esc.append(f"{r['package']} {r['to']} has a different publisher than {r['from']} "
                       f"({r.get('prev_publisher')} to {r.get('publisher')})")
        if r.get("new_install_script"):
            esc.append(f"{r['package']} {r['to']} adds an install script")
    if bot and checks == "none":
        esc.append("no checks ran on this PR, so CI never tested it")
    if bot and not (bot.get("updates")):
        esc.append("could not read which versions this bot PR changes")
    if f.get("compromised"):
        esc += [f"known-compromised version: {c}" for c in f["compromised"]]
    if not bot and kind in ("outside", "member"):
        if checks in ("failed", "not_run", "none") and not docs_only:
            esc.append(f"human PR with checks {checks}")
    if esc:
        reasons += esc
        return done("escalate")

    # close-candidate (human PRs; the model confirms by reading the whole diff)
    if not bot and kind in ("outside", "member"):
        sig = negative_signals(f)
        out["signals"] = sig
        if kind == "outside" and not f.get("linked_issues") and len(sig) >= 3:
            reasons.append(f"{len(sig)} negative signals: " + "; ".join(sig) + " (model: read the whole diff, add the content signal)")
            return done("close-candidate")

    # merge-candidate
    if checks == "passed" and docs_only:
        reasons.append("docs-only change with green checks")
        return done("merge-candidate")
    if bot and checks == "passed":
        if security:
            reasons.append("security update: exempt from the cooldown, not from green CI")
        reasons.append("green on the head SHA, past the cooldown, nothing risky in the lockfile diff")
        return done("merge-candidate")
    if not bot and checks == "passed":
        size = f.get("additions", 0) + f.get("deletions", 0)
        if f.get("linked_issues") and size <= int(cfg.get("small_pr_lines", 200)):
            reasons.append(f"small ({size} lines), linked to #{f['linked_issues'][0]}, green; merge only after reading the whole diff")
            return done("merge-candidate")
        reasons.append("human PR: not small or not linked to an issue; the maintainer decides")
        return done("escalate")
    reasons.append("no rule matched; the maintainer decides")
    return done("escalate")


# Failures with a known mechanical fix (references/prs.md, "Fixing a failing bot PR"). `repairs` is the lockdiff
# reason the fix removes; `how` is said in the verdict comment, so it is fixed text, never PR text.
FIX_RECIPES = {
    "nuget-lock-targets": {
        "repairs": "removed target sections",
        "how": "Dependabot's NuGet updater dropped target sections from packages.lock.json (NU1004 in locked mode); "
               "regenerate the lockfiles on Windows with dotnet restore --force-evaluate",
    },
}


def fix_recipe(f: dict) -> str | None:
    if (f.get("bot") or {}).get("bot") == "dependabot" and any(
            x.get("path", "").endswith("packages.lock.json") and x.get("removed_targets")
            for x in (f.get("lockdiff") or {}).get("files", [])):
        return "nuget-lock-targets"
    return None


# Names typosquats imitate; with the packages the PR bumps, a new package one edit from one of them escalates (D14).
POPULAR = set("react lodash express axios chalk commander debug typescript eslint webpack vite jest mocha moment uuid "
              "dotenv yargs request crypto-js colors minimist semver glob rimraf prettier newtonsoft.json serilog "
              "nunit xunit moq automapper dapper polly".split())


def _one_edit(a: str, b: str) -> bool:
    a, b = re.sub(r"[-_.]", "", a.lower()), re.sub(r"[-_.]", "", b.lower())
    if abs(len(a) - len(b)) > 1:
        return False
    i = next((k for k in range(min(len(a), len(b))) if a[k] != b[k]), min(len(a), len(b)))
    return a[i + 1:] == b[i + 1:] or a[i:] == b[i + 1:] or a[i + 1:] == b[i:]


def transitive_danger(pkg: str, version: str | None, info: dict, known_owners: set | None, bumped: set, cfg: dict) -> list[str]:
    """D14's danger signals for one package a lockfile adds. Odd sources and install scripts escalate on their own
    (lockdiff); an empty list means the package is only a reason in the verdict comment."""
    if info.get("error"):
        return [f"could not check it on its registry ({info['error'][:100]})"]
    if not info.get("exists"):
        return ["not found on its registry"]
    out = []
    owners = set(info.get("owners") or [])
    if not known_owners:
        out.append("could not read the owners of the packages this update moves, so its owner was not compared")
    elif not owners & known_owners:
        out.append(f"owned by {', '.join(sorted(owners)[:3]) or 'nobody listed'}, not by an owner of the packages this update moves")
    created, days = parse_time(info.get("created")), int(cfg.get("new_package_days", 90))
    if created is None:
        out.append("its first publish date is unknown")
    elif (age_days(created) or 0) < days:
        out.append(f"first published {day(created)}, under {days} days ago")
    near = sorted(k for k in POPULAR | bumped if k.lower() != pkg.lower() and len(k) >= 5 and _one_edit(pkg, k))
    if near:
        out.append(f"name is one edit from {near[0]}")
    if f"{pkg}@{version}".lower() in {c.lower() for c in cfg.get("compromised") or []}:
        out.append(f"known-compromised version {version}")
    return out


def negative_signals(f: dict) -> list[str]:
    """The mechanical half of the negative-signal score (design 6a). Never proof on its own."""
    sig = []
    if not f.get("linked_issues"):
        sig.append("no linked issue")
    if f.get("author_association") in ("FIRST_TIME_CONTRIBUTOR", "FIRST_TIMER", "NONE"):
        sig.append("first-time author")
    hist = f.get("author_history") or {}
    if (hist.get("repos_with_prs_last_7d") or 0) >= 5:
        sig.append(f"PRs to {hist['repos_with_prs_last_7d']} repos in the last 7 days")
    if (hist.get("prior_prs_here") or {}).get("closed_unmerged", 0) >= 2:
        sig.append("earlier PRs here closed unmerged")
    lock = f.get("lockdiff") or {}
    if any(x.get("new_packages") for x in lock.get("files", [])):
        sig.append("adds dependencies")
    if f.get("deletions", 0) + f.get("additions", 0) > 500 and not f.get("linked_issues"):
        sig.append("large unrequested change")
    return sig


def superseded(facts: list[dict]) -> dict[int, int]:
    """{older PR number: newer PR number} for single-update bot PRs that a newer bot PR for the same package replaced."""
    latest: dict[tuple, int] = {}
    out = {}
    for f in sorted(facts, key=lambda x: x["number"]):
        bot = f.get("bot") or {}
        ups = bot.get("updates") or []
        if len(ups) != 1:
            continue
        directory = "/".join((f.get("head_ref") or "").split("/")[2:-1])  # dependabot/<eco>/<dir...>/<pkg-ver>
        key = (bot.get("ecosystem"), ups[0]["package"], directory)
        if key in latest:
            out[latest[key]] = f["number"]
        latest[key] = f["number"]
    return out
