"""Read a PR's unified diff and say what its lockfile changes add: new transitive packages, packages from git,
tarball or URL sources, a registry change, new install scripts, and removed or added target sections (Dependabot's
NuGet updater dropped the net48 and win-x86 sections from packages.lock.json on 2026-10-13, which a check that looks
only for added packages misses). A lockfile it cannot read is reported as not analysed, never as clean."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

LOCKFILES = {
    "package-lock.json": "npm",
    "npm-shrinkwrap.json": "npm",
    "packages.lock.json": "nuget",
    "packages-lock.json": "upm",  # Unity Packages/packages-lock.json
    "yarn.lock": "yarn",
    "pnpm-lock.yaml": "pnpm",
    "bun.lock": "bun",
    "bun.lockb": "bun",
    "Cargo.lock": "cargo",
    "poetry.lock": "poetry",
    "uv.lock": "uv",
    "Pipfile.lock": "pipenv",
    "composer.lock": "composer",
    "Gemfile.lock": "bundler",
    "go.sum": "go",
}
DEFAULT_REGISTRIES = ("https://registry.npmjs.org/",)
UPM_REGISTRIES = ("https://packages.unity.com", "https://package.openupm.com")


@dataclass
class FileDiff:
    path: str
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    context: list[str] = field(default_factory=list)
    lines: list[tuple] = field(default_factory=list)  # (sign, text) in order; "@" starts a hunk


NEW_PACKAGES = "new packages"


@dataclass
class LockFileDiff:
    path: str
    kind: str
    analysed: bool = True
    new_packages: list[str] = field(default_factory=list)
    removed_packages: list[str] = field(default_factory=list)
    versions: dict = field(default_factory=dict)  # new-side version of each package this diff adds or moves
    removed_targets: list[str] = field(default_factory=list)
    added_targets: list[str] = field(default_factory=list)
    odd_sources: list[str] = field(default_factory=list)
    new_install_scripts: int = 0

    def flags(self) -> list[str]:
        out = []
        if not self.analysed:
            out.append(f"{self.path}: {self.kind} lockfile not analysed by everkeep")
        if self.new_packages:
            out.append(f"{self.path}: {NEW_PACKAGES} {', '.join(self.new_packages[:8])}" + (" ..." if len(self.new_packages) > 8 else ""))
        if self.removed_targets:
            out.append(f"{self.path}: removed target sections {', '.join(self.removed_targets)}")
        if self.added_targets:
            out.append(f"{self.path}: added target sections {', '.join(self.added_targets)}")
        if self.odd_sources:
            out.append(f"{self.path}: packages from outside the registry {', '.join(self.odd_sources[:5])}")
        if self.new_install_scripts:
            out.append(f"{self.path}: {self.new_install_scripts} new install script(s)")
        return out

    def to_dict(self) -> dict:
        d = dict(self.__dict__)
        d["flags"] = self.flags()
        return d


@dataclass
class LockDiff:
    files: list[LockFileDiff]

    @property
    def reasons(self) -> list[str]:
        return [r for f in self.files for r in f.flags()]

    @property
    def clean(self) -> bool:
        return not self.reasons

    @property
    def unexpected(self) -> list[str]:
        """Findings that stop a multi-repo run from widening (design section 2)."""
        return [f"{f.path}: {s}" for f in self.files for s in f.odd_sources]

    def to_dict(self) -> dict:
        return {"clean": self.clean, "reasons": self.reasons, "files": [f.to_dict() for f in self.files]}


def split_diff(diff: str) -> list[FileDiff]:
    files: list[FileDiff] = []
    cur: FileDiff | None = None
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            m = re.match(r"diff --git a/(.*?) b/(.*)$", line)
            cur = FileDiff(path=m.group(2) if m else line[11:])
            files.append(cur)
            continue
        if cur is not None and line.startswith("@@"):
            cur.lines.append(("@", ""))
        if cur is None or line.startswith(("+++", "---", "index ", "@@", "new file", "deleted file", "similarity",
                                           "rename ", "old mode", "new mode", "Binary files")):
            continue
        if line[:1] in ("+", "-", " "):
            {"+": cur.added, "-": cur.removed, " ": cur.context}[line[0]].append(line[1:])
            cur.lines.append((line[0], line[1:]))
    return files


def _indent(s: str) -> int:
    return len(s) - len(s.lstrip(" "))


def _keys(lines: list[str], indent: int | None = None, pattern: str = r'^\s*"([^"]+)":\s*\{') -> set[str]:
    rx = re.compile(pattern)
    out = set()
    for s in lines:
        m = rx.match(s)
        if m and (indent is None or _indent(s) == indent):
            out.add(m.group(1))
    return out


def _versions(fd: FileDiff, key: str, indent: int, name: str) -> dict:
    """{package: version} for each package whose version line this diff adds, read in order (a key line opens a
    package; a hunk boundary closes it)."""
    out, cur = {}, None
    for sign, s in fd.lines:
        m = re.match(key, s) if sign != "-" else None
        if sign == "@" or (m and _indent(s) == indent):
            cur = m.group(1).split("node_modules/")[-1] if m else None
        elif sign == "+" and cur:
            v = re.match(rf'^\s*"{name}":\s*"([^"]+)"', s)
            if v:
                out[cur] = v.group(1)
    return out


def _npm(fd: FileDiff, registries: tuple) -> LockFileDiff:
    r = LockFileDiff(path=fd.path, kind="npm")
    key = r'^\s*"(node_modules/[^"]+)":\s*\{'
    if not _keys(fd.added + fd.removed + fd.context, pattern=key):
        if fd.added or fd.removed:
            r.analysed = False  # lockfile v1 or something else; never call it clean
        return r
    added, removed = _keys(fd.added, pattern=key), _keys(fd.removed, pattern=key)
    r.new_packages = sorted(k.split("node_modules/")[-1] for k in added - removed)
    r.removed_packages = sorted(k.split("node_modules/")[-1] for k in removed - added)
    r.versions = _versions(fd, key, 4, "version")
    for s in fd.added:
        m = re.search(r'"resolved":\s*"([^"]+)"', s)
        if m and not m.group(1).startswith(registries):
            r.odd_sources.append(m.group(1))
    r.new_install_scripts = max(0, sum('"hasInstallScript": true' in s for s in fd.added)
                                - sum('"hasInstallScript": true' in s for s in fd.removed))
    return r


def _nuget(fd: FileDiff) -> LockFileDiff:
    r = LockFileDiff(path=fd.path, kind="nuget")
    added_t, removed_t = _keys(fd.added, 4), _keys(fd.removed, 4)
    r.removed_targets = sorted(removed_t - added_t)
    r.added_targets = sorted(added_t - removed_t)
    added_p, removed_p = _keys(fd.added, 6), _keys(fd.removed, 6)
    r.new_packages = sorted(added_p - removed_p - set(_keys(fd.context, 6)))
    r.removed_packages = sorted(removed_p - added_p)
    r.versions = _versions(fd, r'^\s*"([^"]+)":\s*\{', 6, "resolved")
    return r


def _upm(fd: FileDiff) -> LockFileDiff:
    r = LockFileDiff(path=fd.path, kind="upm")
    added_p, removed_p = _keys(fd.added, 4), _keys(fd.removed, 4)
    r.new_packages = sorted(added_p - removed_p - set(_keys(fd.context, 4)))
    r.removed_packages = sorted(removed_p - added_p)
    for s in fd.added:
        m = re.search(r'"(?:url|source)":\s*"([^"]+)"', s)
        if m and m.group(1) not in ("registry", "builtin", "embedded", "local") and not m.group(1).startswith(UPM_REGISTRIES):
            r.odd_sources.append(m.group(1))
    return r


def analyse(diff: str, registries: tuple = DEFAULT_REGISTRIES) -> LockDiff:
    out = []
    for fd in split_diff(diff):
        base = fd.path.rsplit("/", 1)[-1]
        kind = LOCKFILES.get(base)
        if kind is None:
            continue
        if kind == "npm":
            out.append(_npm(fd, registries))
        elif kind == "nuget":
            out.append(_nuget(fd))
        elif kind == "upm":
            out.append(_upm(fd))
        else:
            out.append(LockFileDiff(path=fd.path, kind=kind, analysed=False))
    return LockDiff(files=out)
