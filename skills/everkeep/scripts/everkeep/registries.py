"""Registry facts: when a version was published and by whom, straight from each registry's own data. The cooldown is
measured from these times, never from a bot's or package manager's age setting (Renovate skipped its age gate on
digest updates, CVE-2026-88884; pnpm 10.14 ignored minimum-release-age in the Nx Console incident)."""

from __future__ import annotations

import gzip
import json
import urllib.error
import urllib.parse
import urllib.request

from . import VERSION

UA = f"everkeep/{VERSION} (+https://github.com/m4bwav/everkeep)"
_CACHE: dict[str, object] = {}


class FetchError(Exception):
    pass


def fetch_json(url: str, timeout: float = 20) -> object:
    if url in _CACHE:
        return _CACHE[url]
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json", "Accept-Encoding": "gzip"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            if resp.headers.get("Content-Encoding") == "gzip" or raw[:2] == b"\x1f\x8b":
                raw = gzip.decompress(raw)
    except urllib.error.HTTPError as e:
        raise FetchError(f"{url}: HTTP {e.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise FetchError(f"{url}: {e}") from None
    data = json.loads(raw.decode("utf-8"))
    _CACHE[url] = data
    return data


def _norm(v: str) -> str:
    return (v or "").strip().lstrip("vV").lower()


def npm_release(pkg: str, version: str) -> dict:
    doc = fetch_json("https://registry.npmjs.org/" + urllib.parse.quote(pkg, safe="@"))
    v = _norm(version)
    meta = (doc.get("versions") or {}).get(v) or {}
    user = meta.get("_npmUser") or {}
    return {"published": (doc.get("time") or {}).get(v), "publisher": user.get("name"),
            "trusted_publisher": bool(user.get("trustedPublisher")), "exists": bool(meta),
            "has_install_script": bool(meta.get("hasInstallScript") or any(
                k in (meta.get("scripts") or {}) for k in ("preinstall", "install", "postinstall")))}


def nuget_release(pkg: str, version: str) -> dict:
    url = f"https://api.nuget.org/v3/registration5-gz-semver2/{pkg.lower()}/index.json"
    index = fetch_json(url)
    want = _norm(version)
    for page in index.get("items", []):
        items = page.get("items")
        if items is None:
            lower, upper = _norm(page.get("lower", "")), _norm(page.get("upper", ""))
            if not (_vkey(lower) <= _vkey(want) <= _vkey(upper)):
                continue
            items = fetch_json(page["@id"]).get("items", [])
        for it in items:
            entry = it.get("catalogEntry") or {}
            if _norm(entry.get("version", "")) == want:
                return {"published": entry.get("published"), "publisher": None, "trusted_publisher": None,
                        "exists": True, "listed": entry.get("listed", True)}
    return {"published": None, "exists": False}


def package_facts(eco: str, name: str) -> dict:
    """{exists, owners, created} for a package as a whole, or {error}: scope's ownership test and D14's checks on a
    package a lockfile adds. Owners are npm maintainers or nuget.org owners; created is the first publish time."""
    try:
        if eco == "npm":
            doc = fetch_json("https://registry.npmjs.org/" + urllib.parse.quote(name, safe="@"))
            return {"exists": bool(doc.get("versions")), "created": (doc.get("time") or {}).get("created"),
                    "owners": sorted({(m.get("name") or "").lower() for m in doc.get("maintainers") or []})}
        if eco == "nuget":
            hits = fetch_json(f"https://azuresearch-usnc.nuget.org/query?q=packageid:{name}&prerelease=true").get("data", [])
            if not hits:
                return {"exists": False, "owners": []}
            out = {"exists": True, "created": None, "owners": sorted({str(o).lower() for o in hits[0].get("owners") or []})}
            try:  # unlisted versions are dated 1900-01-01
                page = fetch_json(f"https://api.nuget.org/v3/registration5-gz-semver2/{name.lower()}/index.json")["items"][0]
                dates = [(it.get("catalogEntry") or {}).get("published") or "" for it in
                         page.get("items") or fetch_json(page["@id"]).get("items", [])]
                out["created"] = min((d for d in dates if d and not d.startswith("1900")), default=None)
            except (FetchError, KeyError, IndexError):
                pass  # created stays unknown, which D14 reads as a danger signal
            return out
    except FetchError as e:
        return {"exists": False, "owners": []} if "HTTP 404" in str(e) else {"error": str(e)}
    except (ValueError, KeyError, IndexError, AttributeError, TypeError):
        return {"error": f"unreadable registry data for {name}"}
    return {"error": f"no package lookup for ecosystem {eco}"}


def pypi_release(pkg: str, version: str) -> dict:
    doc = fetch_json(f"https://pypi.org/pypi/{urllib.parse.quote(pkg)}/{urllib.parse.quote(_norm(version))}/json")
    urls = doc.get("urls") or []
    return {"published": urls[0].get("upload_time_iso_8601") if urls else None, "exists": True, "publisher": None}


def dotnet_sdk_release(version: str) -> dict:
    v = _norm(version)
    channel = ".".join(v.split(".")[:2])
    doc = fetch_json(f"https://builds.dotnet.microsoft.com/dotnet/release-metadata/{channel}/releases.json")
    for rel in doc.get("releases", []):
        sdks = [s.get("version") for s in rel.get("sdks") or []] + [(rel.get("sdk") or {}).get("version")]
        if v in sdks:
            return {"published": rel.get("release-date") + "T00:00:00Z", "exists": True, "publisher": "Microsoft"}
    return {"published": None, "exists": False}


def endoflife(product: str) -> list:
    data = fetch_json(f"https://endoflife.date/api/v1/products/{product}/")
    return (data.get("result") or {}).get("releases", []) if isinstance(data, dict) else []


def _vkey(v: str) -> tuple:
    out = []
    for part in v.split("-")[0].split("."):
        try:
            out.append(int(part))
        except ValueError:
            out.append(0)
    return tuple(out + [0] * (4 - len(out)))


# Dependabot's directory names in its branch (dependabot/<ecosystem>/...) and Renovate's managers, to everkeep's names.
ECOSYSTEMS = {"npm_and_yarn": "npm", "npm": "npm", "nuget": "nuget", "github_actions": "actions",
              "dotnet_sdk": "dotnet-sdk", "pip": "pypi", "uv": "pypi", "poetry": "pypi"}


def release_facts(ecosystem: str, package: str, version: str, provider=None) -> dict:
    """{published, publisher, trusted_publisher, exists, source} or {error} for one version."""
    try:
        if ecosystem == "npm":
            facts = npm_release(package, version)
        elif ecosystem == "nuget":
            facts = nuget_release(package, version)
        elif ecosystem == "pypi":
            facts = pypi_release(package, version)
        elif ecosystem == "dotnet-sdk":
            facts = dotnet_sdk_release(version)
        elif ecosystem == "actions" and provider is not None:
            repo_path = "/".join(package.split("/")[:2])
            tag = version if version.startswith("v") else f"v{version}"
            published = provider.release_published(repo_path, tag)
            facts = {"published": published, "exists": published is not None, "publisher": repo_path.split("/")[0]}
        else:
            return {"error": f"no publish-time lookup for ecosystem {ecosystem or 'unknown'}"}
    except FetchError as e:
        return {"error": str(e)}
    facts["source"] = ecosystem
    return facts
