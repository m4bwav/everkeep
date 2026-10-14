"""The modernization gap table (design section 9, duty 4) and the dated deadlines checked on every run.

Provider-neutral checks read files through the adapter; settings come from repo_settings. Deep checks call
package-modernize's own scripts by path and say "not checked" when it is not installed, never skip silently."""

from __future__ import annotations

import os
import re
from pathlib import Path

from .providers.registry import get_provider
from .util import EverkeepError, now, parse_time, run

# (date, what, how to find it): listed at the top of the digest until they pass.
DEADLINES = {
    "pull_request_target": ("2026-11-02", "pull_request_target is blocked by default on public repos without an event policy"),
    "nuget_key": ("2026-11-01", "NuGet API keys created before 2026-08-17 expire; publish through trusted publishing first"),
    "dotnet_8_9": ("2026-11-10", ".NET 8 and 9 reach end of support; move to .NET 10"),
    "unity_60": ("2026-10-31", "Unity 6.0 LTS support ends; move to Unity 6.3 LTS"),
    "npm_token": ("2027-01-31", "npm stops accepting tokens that bypass 2FA; publish through trusted publishing"),
    "node_20": ("2026-04-30", "Node 20 is end of life; test on 22, 24 and 26"),
}
GATE_FILES = {"scripts/size_check.py", "scripts/budget.py", ".size-limit.json", ".size-limit.js", ".size-limit.cjs"}
_USES = re.compile(r"^\s*-?\s*uses:\s*['\"]?([^'\"\s#]+)", re.M)


def _text(provider, repo, path) -> str:
    raw = provider.file(repo.id, path)
    return raw.decode("utf-8", "replace") if raw else ""


def package_modernize_dir(cfg: dict) -> Path | None:
    for cand in (cfg.get("package_modernize"), os.environ.get("PACKAGE_MODERNIZE_HOME"),
                 Path.home() / ".claude" / "skills" / "package-modernize"):
        if cand and (Path(cand) / "scripts").is_dir():
            return Path(cand)
    return None


def audit(entry: dict, store, deep: bool = False) -> dict:
    cfg = store.config()
    repo = entry["repo"]
    p = get_provider(repo.id, cfg)
    caps = p.capabilities()
    try:
        paths = p.tree(repo.id, repo.default_branch)
    except EverkeepError as e:
        return {"repo": entry["id"], "error": str(e), "gaps": [], "deadlines": [], "not_checked": []}
    pset = set(paths)
    lower = {x.lower(): x for x in paths}
    public = repo.visibility == "public"
    packages = entry.get("packages") or []
    ecos = entry.get("ecosystems") or []
    rows, not_checked, deadlines = [], [], []

    def row(name, status, detail="", fix=""):
        rows.append({"gap": name, "status": status, "detail": detail, "fix": fix})

    workflows = [x for x in paths if re.match(r"^\.github/workflows/[^/]+\.ya?ml$", x)]
    wf_text = {w: _text(p, repo, w) for w in workflows}
    all_wf = "\n".join(wf_text.values())

    def has_any(*names):
        return next((lower[n.lower()] for n in names if n.lower() in lower), None)

    row("SECURITY.md", "ok" if has_any("SECURITY.md", ".github/SECURITY.md", "docs/SECURITY.md") else "gap", "",
        "cheap: the tiered template")
    readme = has_any("README.md", "README", "readme.md", "README.rst")
    readme_text = _text(p, repo, readme) if readme else ""
    row("README banner", "ok" if ".github/images/banner" in readme_text else "gap" if readme else "gap",
        "" if readme else "no README", "banner through an image generator")
    if caps.has("topics"):
        row("topics", "ok" if len(repo.topics) >= 5 else "gap", f"{len(repo.topics)} topics", "cheap: topics.py suggest")
    if "plugin" in ecos:
        row("icon", "ok" if ".claude-plugin/icon.png" in pset else "gap", "", "cheap: make-icon.py")
    elif any(x.startswith("nuget:") for x in packages):
        # F# and VB libraries pack too (an .fsproj icon read as missing); src/ first, where the packed project lives.
        props = sorted((x for x in paths if x.endswith((".csproj", ".fsproj", ".vbproj", "Directory.Build.props"))),
                       key=lambda x: (not x.startswith("src/"), x))[:6]
        icon = any("<PackageIcon>" in _text(p, repo, x) for x in props)
        row("icon", "ok" if icon else "gap", "PackageIcon", "cheap: make-icon.py")
    dep = has_any(".github/dependabot.yml", ".github/dependabot.yaml", "renovate.json", ".github/renovate.json")
    if dep:
        dtext = _text(p, repo, dep)
        cool = "cooldown" in dtext or "minimumReleaseAge" in dtext
        row("dependency bot with cooldown", "ok" if cool else "gap", dep + ("" if cool else ": no cooldown"), "cheap")
    else:
        row("dependency bot with cooldown", "gap", "no dependabot.yml or renovate.json", "cheap")
    if workflows:
        unpinned = sorted({u for u in _USES.findall(all_wf) if not u.startswith(("./", "docker://"))
                           and not re.search(r"@[0-9a-f]{40}$", u)})
        row("actions pinned by SHA", "gap" if unpinned else "ok", ", ".join(unpinned[:6]), "cheap: pin with version comments")
        noperm = [w for w, t in wf_text.items() if not re.search(r"^permissions:", t, re.M)]
        row("read-only workflow token", "gap" if noperm else "ok", ", ".join(noperm[:4]), "cheap: top-level permissions: contents: read")
    s = {}
    try:
        s = p.repo_settings(repo.id)
    except EverkeepError as e:
        not_checked.append(f"repo settings: {e}")
    for key, label, fix in (("dependency_alerts", "Dependabot alerts", "switch on (D11)"),
                            ("security_updates", "Dependabot security updates", "switch on (D11)"),
                            ("secret_scanning", "secret scanning", "switch on (D11)"),
                            ("push_protection", "push protection", "switch on (D11)"),
                            ("private_vuln_reporting", "private vulnerability reporting", "switch on (D11)")):
        v = s.get(key)
        if key in ("secret_scanning", "push_protection") and not public and v is None:
            row(label, "n/a", "not offered for private repos on this plan")
            continue
        row(label, "ok" if v is True else "gap" if v is False else "unknown", "", fix)
    if public:
        cs = s.get("code_scanning_default")
        row("CodeQL default setup", "ok" if cs == "configured" else "gap" if cs else "unknown", str(cs or ""), "switch on (D11)")
        cap = s.get("pr_creation_cap")
        row("open-PR cap for users without write access", "ok" if isinstance(cap, dict) and cap.get("enabled") else "gap",
            "", "switch on (D11)")
    rs = s.get("rulesets")
    row("ruleset on the default branch", "ok" if rs else "gap" if rs == 0 else "unknown", "", "ask first (D11)")
    if packages:
        pub = [w for w, t in wf_text.items() if re.search(r"npm publish|nuget push|dotnet nuget push|pypa/gh-action-pypi-publish|twine upload", t)]
        if not pub:
            row("trusted publishing", "unknown", "no publish workflow found", "package-modernize")
        else:
            tokens = [w for w in pub if re.search(r"secrets\.(NPM_TOKEN|NODE_AUTH_TOKEN|NUGET_API_KEY|NUGET_KEY|PYPI_TOKEN|PYPI_API_TOKEN)", wf_text[w])]
            row("trusted publishing", "gap" if tokens else "ok", ", ".join(tokens), "package-modernize")
            if any("nuget push" in wf_text[w] for w in tokens):
                deadlines.append(("nuget_key", ", ".join(tokens)))
            if any("npm publish" in wf_text[w] for w in tokens):
                deadlines.append(("npm_token", ", ".join(tokens)))
        if public and caps.has("wiki"):
            w = p.wiki_exists(repo.id)
            row("wiki", "ok" if w else "gap" if w is False else "unknown", "", "wikiwright")
        gate = bool(GATE_FILES & pset) or ("package.json" in pset and "size-limit" in _text(p, repo, "package.json"))
        row("size-budget gate", "ok" if gate else "gap", "", "manual: thresholds with the maintainer")
        golden = any(re.search(r"(^|/)golden/|Golden", x) for x in paths)
        row("golden recording and gated release", "ok" if golden else "gap", "", "package-modernize kickoff")
    elif "plugin" in ecos:
        gate = bool(GATE_FILES & pset)
        row("size-budget gate", "ok" if gate else "gap", "", "manual")
    agents = "AGENTS.md" in pset
    claude = _text(p, repo, "CLAUDE.md").lstrip().splitlines()[:1] if "CLAUDE.md" in pset else None
    ok = agents and (claude is None or claude == ["@AGENTS.md"])
    row("AGENTS.md with the @AGENTS.md import", "ok" if ok else "gap",
        "" if agents else "no AGENTS.md" if claude is None else "CLAUDE.md does not start with @AGENTS.md", "cheap")
    contrib = has_any("CONTRIBUTING.md", ".github/CONTRIBUTING.md", "docs/CONTRIBUTING.md")
    ai = contrib and re.search(r"\bAI\b|agent|LLM|generated", _text(p, repo, contrib))
    row("CONTRIBUTING.md with an AI-contribution policy", "ok" if ai else "gap",
        "" if contrib else "no CONTRIBUTING.md", "cheap: closing comments need a written rule to cite")

    # dated deadlines
    if public and "pull_request_target" in all_wf:
        deadlines.append(("pull_request_target", ", ".join(w for w, t in wf_text.items() if "pull_request_target" in t)))
    proj = [x for x in paths if x.endswith((".csproj", ".fsproj", "Directory.Build.props", "global.json"))][:12]
    old_net = [x for x in proj if re.search(r"net[89]\.0|\"version\":\s*\"[89]\.", _text(p, repo, x))]
    if old_net:
        deadlines.append(("dotnet_8_9", ", ".join(old_net[:4])))
    if re.search(r"node-version:\s*['\"]?(18|20)(\.|['\"\s]|$)", all_wf, re.M):
        deadlines.append(("node_20", "workflows still test Node 20 or older"))
    pv = next((x for x in paths if x.endswith("ProjectSettings/ProjectVersion.txt")), None)
    if pv and "6000.0." in _text(p, repo, pv):
        deadlines.append(("unity_60", pv))

    if deep:
        pm = package_modernize_dir(cfg)
        if pm is None:
            not_checked.append("deep gap checks: package-modernize not installed (PACKAGE_MODERNIZE_HOME)")
        else:
            t = run(["python", str(pm / "scripts" / "topics.py"), "check", repo.id.path], timeout=120)
            row("topics (package-modernize topics.py)", "ok" if t.returncode == 0 else "gap", t.stdout.strip()[-300:], "cheap")
            if entry.get("clone"):
                lw = run(["bash", str(pm / "scripts" / "lint-workflows.sh"), entry["clone"]], timeout=600)
                row("workflow lint (actionlint, shellcheck, zizmor)", "ok" if lw.returncode == 0 else "gap",
                    lw.stdout.strip()[-400:], "fix the findings")
            else:
                not_checked.append("workflow lint: no local clone (config clones or clone_roots)")
    today = now()
    dl = []
    for key, where in deadlines:
        date, what = DEADLINES[key]
        passed = parse_time(date) < today
        dl.append({"key": key, "date": date, "what": what, "where": where, "passed": passed})
    return {"repo": entry["id"], "gaps": rows, "deadlines": dl, "not_checked": not_checked}
