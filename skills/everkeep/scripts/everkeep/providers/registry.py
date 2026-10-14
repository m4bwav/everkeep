"""Map remote URLs and command-line repo arguments to provider-qualified identities, and identities to adapters.

Only GitHub is built. Every other recognised host parses to its own identity (so the message can name it) and then
raises ProviderNotSupported, and the command exits 3 having done nothing else."""

from __future__ import annotations

import os
import re
from urllib.parse import unquote, urlsplit

from ..util import EverkeepError
from .base import Provider, ProviderNotSupported, RepoId

BUILT = {"github"}
PROVIDER_NAMES = {"github", "gitlab", "bitbucket", "azure", "codeberg", "forgejo", "gitea"}
KNOWN_HOSTS = {
    "github.com": "github",
    "www.github.com": "github",
    "gitlab.com": "gitlab",
    "bitbucket.org": "bitbucket",
    "dev.azure.com": "azure",
    "ssh.dev.azure.com": "azure",
    "vs-ssh.visualstudio.com": "azure",
    "codeberg.org": "codeberg",
}
# Hosts with an identity that needs no host part (the public instance of each provider).
PUBLIC_INSTANCE = {"github.com": "github", "www.github.com": "github", "gitlab.com": "gitlab",
                   "bitbucket.org": "bitbucket", "codeberg.org": "codeberg"}

_SCP = re.compile(r"^(?:(?P<user>[^@/]+)@)?(?P<host>[^:/]+):(?P<path>(?!//).+)$")


class UnknownHost(EverkeepError):
    exit_code = 3


def _strip_git(path: str) -> str:
    path = path.strip("/")
    return path[:-4] if path.endswith(".git") else path


def _azure_path(host: str, path: str, user: str | None) -> str:
    parts = [unquote(p) for p in path.strip("/").split("/") if p]
    if parts and parts[0] == "v3":  # ssh forms: v3/org/project/repo
        parts = parts[1:]
    if "_git" in parts:
        i = parts.index("_git")
        before, repo = parts[:i], parts[i + 1] if i + 1 < len(parts) else ""
        if host.endswith(".visualstudio.com") and host != "vs-ssh.visualstudio.com":
            org = host.split(".")[0]
            before = [p for p in before if p.lower() != "defaultcollection"]
            return "/".join([org, *before, repo])
        return "/".join([*before, repo])
    return "/".join(parts)


def parse_remote(url: str, hosts: dict | None = None) -> RepoId:
    """Parse a git remote URL (HTTPS, ssh://, or scp-like) into a RepoId. `hosts` pins host -> provider."""
    hosts = {k.lower(): v for k, v in (hosts or {}).items()}
    url = url.strip()
    user = None
    if "://" in url:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        user = parts.username
        path = parts.path
    else:
        m = _SCP.match(url)
        if not m:
            raise UnknownHost(f"not a remote URL: {url}")
        host, path, user = m.group("host").lower(), m.group("path"), m.group("user")
    provider = hosts.get(host) or KNOWN_HOSTS.get(host)
    if provider is None and host.endswith(".visualstudio.com"):
        provider = "azure"
    if provider is None:
        raise UnknownHost(f"unknown git host {host}: pin it to a provider in ~/.everkeep/config.json "
                          f'("hosts": {{"{host}": "gitlab"}}), or ask for it at '
                          "https://github.com/m4bwav/everkeep/issues/new?template=provider.md")
    if provider == "azure":
        rpath = _azure_path(host, path, user)
        return RepoId("azure", rpath)
    rpath = _strip_git(unquote(path))
    if not rpath or ("/" not in rpath):
        raise UnknownHost(f"no owner/name in remote URL: {url}")
    if PUBLIC_INSTANCE.get(host) == provider:
        return RepoId(provider, rpath)
    return RepoId(provider, rpath, host)


def parse_repo_arg(arg: str, default_owner: str | None = None, hosts: dict | None = None,
                   default_provider: str = "github") -> RepoId:
    """`github:owner/name`, `gitea@host:owner/name`, a URL, `owner/name`, or a bare `name` (the default owner's)."""
    arg = arg.strip()
    m = re.match(r"^(?P<prov>[a-z]+)(?:@(?P<host>[^:]+))?:(?P<path>[^/].*)$", arg)
    if m and m.group("prov") in PROVIDER_NAMES:
        return RepoId(m.group("prov"), _strip_git(m.group("path")), m.group("host"))
    if "://" in arg or re.match(r"^[^@/\s]+@[^:]+:", arg):
        return parse_remote(arg, hosts)
    if "/" in arg:
        return RepoId(default_provider, _strip_git(arg))
    if not default_owner:
        raise EverkeepError(f"cannot tell whose repo {arg} is: write it as owner/{arg}")
    return RepoId(default_provider, f"{default_owner}/{arg}")


_CACHE: dict = {}


def get_provider(repo: RepoId | str, config: dict | None = None) -> Provider:
    """The adapter for an identity. EVERKEEP_FAKE_PROVIDER (a fixture path) swaps GitHub for the fake adapter."""
    name = repo.provider if isinstance(repo, RepoId) else repo
    host = repo.host if isinstance(repo, RepoId) else None
    if name not in BUILT:
        raise ProviderNotSupported(name, str(repo) if isinstance(repo, RepoId) else "")
    fixture = os.environ.get("EVERKEEP_FAKE_PROVIDER")
    key = (name, host, fixture)
    if key not in _CACHE:
        if fixture:
            from .fake import FakeProvider
            _CACHE[key] = FakeProvider.from_file(fixture)
        else:
            from .github import GitHubProvider
            _CACHE[key] = GitHubProvider(host=host, config=config or {})
    return _CACHE[key]


def reset_cache() -> None:
    _CACHE.clear()
