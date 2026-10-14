"""Scope (design section 2): no arguments means the repo in the current directory; --repo, --select, --filter and
--all widen it. Resolution prints the list before anything acts. Also the per-repo facts every command shows with
it: tier, ecosystems, registry packages and the local clone."""

from __future__ import annotations

import csv
import fnmatch
import json
import re
from pathlib import Path

from .providers.base import Repo, RepoId
from .providers.registry import get_provider, parse_remote, parse_repo_arg
from .util import EverkeepError, ScopeNeeded, age_days, parse_time, run

TIER_RANK = {"low": 0, "medium": 1, "high": 2, "shared": 2}
FILTER_KEYS = ("provider", "owner", "ecosystem", "package", "topic", "name", "visibility", "tier", "pushed", "has")


def add_scope_args(p) -> None:
    g = p.add_argument_group("scope (default: the repo in the current directory)")
    g.add_argument("--repo", action="append", default=[], metavar="REPO",
                   help="github:owner/name, owner/name or name (repeatable)")
    g.add_argument("--select", metavar="NAME", help="a saved selection")
    g.add_argument("--filter", action="append", default=[], metavar="KEY=VALUE",
                   help="ANDed filters over the account: " + ", ".join(FILTER_KEYS))
    g.add_argument("--all", action="store_true", help="every repo of every configured account")
    g.add_argument("--include-forks", action="store_true")
    g.add_argument("--include-archived", action="store_true")
    g.add_argument("--include-private", action="store_true")
    g.add_argument("--exclude-private", action="store_true", help="override an overlay that includes private repos")


def scope_spec(args) -> dict:
    return {k: getattr(args, k, None) for k in ("repo", "select", "filter", "all", "include_forks",
                                                "include_archived", "include_private", "exclude_private")}


# ------------------------------------------------------------------ resolution

def current_repo(cwd: str | Path, hosts: dict) -> RepoId:
    p = run(["git", "-C", str(cwd), "remote", "get-url", "origin"], timeout=20)
    if p.returncode != 0:
        raise ScopeNeeded("not inside a git repository with an origin remote: name one with --repo, or use "
                          "--select NAME or --all")
    return parse_remote(p.stdout.strip(), hosts)


def _accounts(cfg: dict) -> list[tuple[str, str]]:
    gh = get_provider("github", cfg)
    out = [("github", gh.whoami())]
    out += [("github", a) for a in (cfg.get("accounts") or {}).get("github", []) if a]
    return out


def _includes(args, cfg: dict, filters: list[tuple[str, str]], spec: dict | None = None) -> dict:
    inc = dict(cfg.get("include") or {})
    inc.update((spec or {}).get("include") or {})
    for k in ("forks", "archived", "private"):
        if getattr(args, f"include_{k}", False):
            inc[k] = True
    if getattr(args, "exclude_private", False):
        inc["private"] = False
    if ("visibility", "private") in filters:
        inc["private"] = True
    return inc


def resolve(args, store, cwd: str | Path = ".") -> list[dict]:
    cfg = store.config()
    hosts = cfg.get("hosts") or {}
    repos: list[Repo] = []
    filters = [_parse_filter(f) for f in (getattr(args, "filter", None) or [])]
    spec = None
    if getattr(args, "select", None):
        sels = store.selections()
        if args.select not in sels:
            raise EverkeepError(f"no selection {args.select}; saved: {', '.join(sorted(sels)) or 'none'}")
        spec = sels[args.select]
        filters += [_parse_filter(f) for f in spec.get("filter", [])]
    if getattr(args, "repo", None) or (spec and spec.get("repos")):
        names = list(args.repo or []) + list((spec or {}).get("repos") or [])
        for name in names:
            rid = repo_id(name, cfg)
            repos.append(get_provider(rid, cfg).get_repo(rid))
    elif getattr(args, "all", False) or filters or (spec and (spec.get("all") or spec.get("filter"))):
        inc = _includes(args, cfg, filters, spec)
        seen = set()
        for provider_name, account in _accounts(cfg):
            for r in get_provider(provider_name, cfg).list_repos(account, inc["forks"], inc["archived"], inc["private"]):
                if str(r.id) not in seen:
                    seen.add(str(r.id))
                    repos.append(r)
    else:
        rid = current_repo(cwd, hosts)
        repos.append(get_provider(rid, cfg).get_repo(rid))
    entries = [describe(r, store) for r in repos]
    entries = [e for e in entries if all(_match(e, k, v, store) for k, v in filters)]
    entries.sort(key=lambda e: (TIER_RANK.get(e["tier"], 1), e["id"].lower()))
    return entries


def repo_id(name: str, cfg: dict) -> RepoId:
    """A repo argument as an id; a bare name is the logged-in account's repo, the same for every command."""
    owner = get_provider("github", cfg).whoami() if "/" not in name and ":" not in name else None
    return parse_repo_arg(name, owner, cfg.get("hosts"))


def _parse_filter(text: str) -> tuple[str, str]:
    if "=" not in text:
        raise EverkeepError(f"filter {text!r} is not KEY=VALUE")
    k, v = text.split("=", 1)
    k = k.strip().lower()
    if k not in FILTER_KEYS:
        raise EverkeepError(f"unknown filter key {k}; keys: {', '.join(FILTER_KEYS)}")
    return k, v.strip()


def _match(e: dict, key: str, value: str, store) -> bool:
    if "," in value:  # tier=low,medium: any of them
        return any(_match(e, key, v.strip(), store) for v in value.split(",") if v.strip())
    r: Repo = e["repo"]
    if key == "provider":
        return r.id.provider == value
    if key == "owner":
        return r.id.owner.lower() == value.lower()
    if key == "ecosystem":
        return value in e["ecosystems"] or (value == "none" and not e["ecosystems"])
    if key == "package":  # publishes to this registry (npm, nuget, openupm, pypi)
        return any(p.startswith(value + ":") for p in e["packages"])
    if key == "topic":
        return value in r.topics
    if key == "name":
        return fnmatch.fnmatch(r.id.name.lower(), value.lower())
    if key == "visibility":
        return r.visibility == value
    if key == "tier":
        return e["tier"] == value
    if key == "pushed":
        m = re.match(r"^([<>])(\d+)d$", value)
        if not m:
            raise EverkeepError("pushed takes <Nd or >Nd, for example pushed=<90d")
        age = age_days(parse_time(r.pushed_at)) or 0
        return age < int(m.group(2)) if m.group(1) == "<" else age > int(m.group(2))
    if key == "has":
        p = get_provider(r.id, store.config())
        if value in ("open-prs", "bot-prs", "failing-prs"):
            prs = p.list_open_prs(r.id)
            if value == "open-prs":
                return bool(prs)
            bots = [x for x in prs if x.author_kind == "bot"]
            if value == "bot-prs":
                return bool(bots)
            return any(p.pr_detail(r.id, x.number).checks.state in ("failed", "not_run") for x in bots)
        if value == "alerts":
            try:
                return bool(p.alerts(r.id, "dependency"))
            except EverkeepError:
                return False
        if value == "no-kb":
            return not (e["clone"] and (Path(e["clone"]) / "ai-docs").is_dir())
        raise EverkeepError("has takes open-prs, bot-prs, failing-prs, alerts or no-kb")
    return True


# ------------------------------------------------------------------ per-repo facts

ECOSYSTEM_FILES = [
    (r"(^|/)package\.json$", "npm"), (r"\.(cs|fs|vb)proj$|(^|/)global\.json$|\.sln$|\.slnx$|(^|/)Directory\.Build\.props$", "nuget"),
    (r"(^|/)pyproject\.toml$|(^|/)setup\.py$|(^|/)requirements[^/]*\.txt$", "pypi"),
    (r"^\.claude-plugin/plugin\.json$|^plugin\.json$", "plugin"), (r"(^|/)ProjectSettings/ProjectVersion\.txt$", "unity"),
    (r"(^|/)Cargo\.toml$", "crates"), (r"(^|/)go\.mod$", "go")]


# Folders whose project files are not the repo's own product: templates, fixtures, samples, tests, docs.
_NOT_PRODUCT = re.compile(r"(^|/)(node_modules|templates?|fixtures?|evals?|examples?|samples?|tests?|benchmarks?|docs?)/", re.I)


def ecosystems_from_tree(paths: list[str]) -> list[str]:
    found = []
    for p in paths:
        if _NOT_PRODUCT.search(p):
            continue
        for rx, eco in ECOSYSTEM_FILES:
            if eco not in found and re.search(rx, p):
                found.append(eco)
    return found


def _on_registry(pkg: str, accounts: dict) -> bool | None:
    """True when the registry has the package (and, when the config names the user's registry accounts, one of them
    owns it); False when it does not; None when it could not be asked."""
    from . import registries as R
    eco, name = pkg.split(":", 1)
    mine = {a.lower() for a in (accounts or {}).get(eco, [])}
    try:
        if eco == "npm":
            doc = R.fetch_json("https://registry.npmjs.org/" + name.replace("/", "%2F"))
            if not doc.get("versions"):
                return False  # unpublished: the name answers but holds nothing
            owners = {(m.get("name") or "").lower() for m in doc.get("maintainers") or []}
        elif eco == "nuget":
            hits = R.fetch_json(f"https://azuresearch-usnc.nuget.org/query?q=packageid:{name}&prerelease=true").get("data", [])
            if not hits:
                return False
            owners = {str(o).lower() for o in hits[0].get("owners") or []}
        elif eco in ("openupm", "pypi"):  # neither lists owners in its JSON; existence is the test
            R.fetch_json(f"https://package.openupm.com/{name}" if eco == "openupm" else f"https://pypi.org/pypi/{name}/json")
            return True
        else:
            return None
    except R.FetchError as e:
        return False if "HTTP 404" in str(e) else None
    except (ValueError, AttributeError):
        return None
    return bool(owners & mine) if mine else True


def published_packages(repo: Repo, paths: list[str], provider, accounts: dict | None = None) -> list[str]:
    """Registry packages the repo publishes: candidates from its own files (npm name unless private, OpenUPM, NuGet
    PackageId or the product project's name), kept when the registry knows them or cannot be asked."""
    cands = []
    if "package.json" in paths:
        try:
            pj = json.loads(provider.file(repo.id, "package.json") or b"{}")
        except ValueError:
            pj = {}
        if pj.get("name") and not pj.get("private"):
            cands.append(("openupm:" if pj.get("unity") else "npm:") + pj["name"])
    if "pyproject.toml" in paths:
        m = re.search(r'^\[project\][^\[]*?^name\s*=\s*"([^"]+)"',
                      (provider.file(repo.id, "pyproject.toml") or b"").decode("utf-8", "replace"), re.M | re.S)
        if m:
            cands.append("pypi:" + m.group(1))
    props = (provider.file(repo.id, "Directory.Build.props") or b"").decode("utf-8", "replace") \
        if "Directory.Build.props" in paths else ""
    projects = [p for p in paths if re.search(r"\.(cs|fs|vb)proj$", p) and not _NOT_PRODUCT.search(p)
                and not re.search(r"\.(Tests?|Benchmarks?|Samples?|Golden\w*)\.\w+proj$", p, re.I)][:6]
    for p in projects:
        raw = (provider.file(repo.id, p) or b"").decode("utf-8", "replace")
        if re.search(r"<IsPackable>\s*false", raw, re.I):
            continue
        m = re.search(r"<PackageId>([^<$]+)</PackageId>", raw) or re.search(r"<PackageId>([^<$]+)</PackageId>", props)
        cands.append("nuget:" + (m.group(1).strip() if m else Path(p).stem))
    return [c for c in dict.fromkeys(cands) if _on_registry(c, accounts or {}) is not False][:4]


def downloads(cfg: dict) -> dict[str, dict]:
    """{"registry:package": {"total": n, "recent": n}} from the newest snapshot rows of repo-traffic's downloads.csv."""
    path = cfg.get("downloads_csv")
    out: dict[str, dict] = {}
    if not path or not Path(path).exists():
        return out
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            key = f"{row.get('registry')}:{row.get('package')}".lower()
            def num(k):
                try:
                    return int(float(row.get(k) or 0))
                except ValueError:
                    return 0
            recent = max(num("last_6_weeks"), num("last_month"), num("last_14_days"))
            if key not in out or (row.get("snapshot") or "") >= out[key]["snapshot"]:
                out[key] = {"snapshot": row.get("snapshot") or "", "total": num("total"), "recent": recent}
    return out


def tier_of(repo: Repo, packages: list[str], me: str, cfg: dict, dl: dict) -> tuple[str, str]:
    tiers = cfg.get("tiers") or {}
    names = {repo.id.name.lower()} | {p.split(":", 1)[-1].lower() for p in packages}
    high = {n.lower() for n in tiers.get("high", [])}
    if names & high:
        return "high", "on the overlay's high-risk list"
    th = tiers.get("thresholds") or {}
    for p in packages:
        d = dl.get(p.lower())
        if d and (d["total"] >= th.get("total", 10 ** 12) or d["recent"] >= th.get("recent", 10 ** 12)):
            return "high", f"{p}: {d['total']} total, {d['recent']} recent downloads"
    own = {me.lower()} | {a.lower() for a in (cfg.get("accounts") or {}).get("github", [])}
    if repo.fork:
        return "shared", "a fork"
    if repo.id.owner.lower() not in own or repo.id.name.lower() in {n.lower() for n in tiers.get("shared", [])}:
        return "shared", "someone else's or shared with other committers"
    if packages:
        return "medium", "publishes " + ", ".join(packages[:3])
    return "low", "publishes nothing"


def find_clone(repo: Repo, cfg: dict) -> str | None:
    clones = cfg.get("clones") or {}
    if str(repo.id) in clones:
        return clones[str(repo.id)]
    for root in cfg.get("clone_roots") or []:
        cand = Path(root) / repo.id.name
        if (cand / ".git").exists():
            p = run(["git", "-C", str(cand), "remote", "get-url", "origin"], timeout=20)
            try:
                if p.returncode == 0 and parse_remote(p.stdout.strip(), cfg.get("hosts")) == repo.id:
                    return str(cand)
            except EverkeepError:
                continue
    return None


def describe(repo: Repo, store) -> dict:
    cfg = store.config()
    provider = get_provider(repo.id, cfg)
    st = store.repo_state(str(repo.id))
    inv = st.get("inventory") or {}
    if inv.get("pushed_at") != repo.pushed_at or inv.get("v") != 3:
        try:
            paths = provider.tree(repo.id, repo.default_branch)
        except EverkeepError:
            paths = []
        inv = {"v": 3, "pushed_at": repo.pushed_at, "ecosystems": ecosystems_from_tree(paths),
               "packages": published_packages(repo, paths, provider, cfg.get("registry_accounts")) + list((cfg.get("packages") or {}).get(repo.id.name, []))}
        st["inventory"] = inv
        store.save_repo_state(str(repo.id), st)
    packages = list(dict.fromkeys(inv["packages"]))
    tier, why = tier_of(repo, packages, provider.whoami(), cfg, downloads(cfg))
    return {"id": str(repo.id), "repo": repo, "tier": tier, "tier_reason": why, "ecosystems": inv["ecosystems"],
            "packages": packages, "clone": find_clone(repo, cfg), "visibility": repo.visibility}


def entry_row(e: dict) -> list:
    return [e["id"], e["tier"], e["visibility"], ", ".join(e["ecosystems"]) or "none", ", ".join(e["packages"]) or "",
            e["clone"] or ""]


ENTRY_HEADERS = ["repo", "tier", "visibility", "ecosystems", "packages", "clone"]
