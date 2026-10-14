"""The provider interface. Everything everkeep does on a host goes through a subclass of Provider; nothing above this
line knows which host it talks to. Plain dataclasses in and out; every write takes `apply` and returns the Action it
took or would take, so dry runs and real runs share one path. See references/providers.md."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any

from ..util import EverkeepError

ISSUE_URL = "https://github.com/m4bwav/everkeep/issues/new?template=provider.md"

CHECK_STATES = ("passed", "failed", "not_run", "pending", "none")


class ProviderNotSupported(EverkeepError):
    exit_code = 3

    def __init__(self, provider: str, repo: str = ""):
        where = f" (repo {repo})" if repo else ""
        super().__init__(f"provider {provider} isn't supported yet{where}; ask for it at {ISSUE_URL}")
        self.provider = provider


class AuthMissing(EverkeepError):
    exit_code = 4

    def __init__(self, provider: str, login_command: str, detail: str = ""):
        super().__init__(f"{provider}: not logged in{': ' + detail if detail else ''}. Run: {login_command}")
        self.login_command = login_command


class RateLimited(EverkeepError):
    exit_code = 5


class Unsupported(EverkeepError):
    """A capability this provider lacks; the duty records a Not checked line with its fallback."""


class GuardRefused(EverkeepError):
    exit_code = 6


class _Dict:
    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class RepoId(_Dict):
    provider: str
    path: str
    host: str | None = None  # set only for a self-hosted instance

    def __str__(self) -> str:
        return f"{self.provider}@{self.host}:{self.path}" if self.host else f"{self.provider}:{self.path}"

    @property
    def owner(self) -> str:
        return self.path.rsplit("/", 1)[0] if "/" in self.path else ""

    @property
    def name(self) -> str:
        return self.path.rsplit("/", 1)[-1]

    def to_dict(self) -> dict:
        return {"id": str(self), "provider": self.provider, "path": self.path, "host": self.host}


@dataclass
class Repo(_Dict):
    id: RepoId
    default_branch: str = "main"
    visibility: str = "public"  # public, private, internal
    fork: bool = False
    archived: bool = False
    pushed_at: str | None = None
    topics: list[str] = field(default_factory=list)
    description: str = ""
    homepage: str = ""

    def to_dict(self) -> dict:
        d = dataclasses.asdict(self)
        d["id"] = str(self.id)
        return d


@dataclass
class Check(_Dict):
    name: str
    state: str  # one of CHECK_STATES except none
    url: str = ""
    raw: str = ""  # the host's own status and conclusion, for the evidence line


@dataclass
class ChecksState(_Dict):
    state: str
    checks: list[Check] = field(default_factory=list)

    def summary(self) -> str:
        counts: dict[str, int] = {}
        for c in self.checks:
            counts[c.state] = counts.get(c.state, 0) + 1
        inner = ", ".join(f"{n} {s}" for s, n in sorted(counts.items()))
        return f"{self.state} ({inner})" if inner else self.state


@dataclass
class PullRequest(_Dict):
    repo: str  # str(RepoId)
    number: int
    title: str  # untrusted
    author: str
    author_kind: str  # bot, owner, member, outside
    is_draft: bool
    head_sha: str
    head_ref: str
    base: str
    labels: list[str]
    created_at: str
    url: str


@dataclass
class FileChange(_Dict):
    path: str
    additions: int = 0
    deletions: int = 0
    status: str = "modified"  # added, modified, deleted, renamed


@dataclass
class PullRequestDetail(_Dict):
    pr: PullRequest
    body: str  # untrusted
    files: list[FileChange]
    linked_issues: list[int]
    checks: ChecksState
    author_association: str  # OWNER, MEMBER, COLLABORATOR, CONTRIBUTOR, FIRST_TIME_CONTRIBUTOR, NONE
    additions: int = 0
    deletions: int = 0


@dataclass
class AuthorHistory(_Dict):
    login: str
    account_created: str | None = None
    repos_with_prs_last_7d: int | None = None
    prior_prs_here: dict = field(default_factory=dict)  # {"merged": n, "closed": n, "open": n}


@dataclass
class Alert(_Dict):
    kind: str  # dependency, code, secret
    id: str
    severity: str = ""
    package: str = ""
    ecosystem: str = ""
    summary: str = ""
    url: str = ""
    state: str = "open"  # open, withdrawn
    fixed_in: str = ""


@dataclass
class Action(_Dict):
    kind: str  # merge, close, comment, label, assign, review, enable, open_pr, verdict
    target: str  # repo#n or repo
    detail: str = ""
    command: str = ""  # what was run or would run
    applied: bool = False
    ok: bool = True
    error: str = ""


@dataclass
class Capabilities(_Dict):
    labels: bool = False
    assignees: bool = False
    reviewers: bool = False
    issues: bool = False
    alerts_dependency: bool = False
    alerts_code: bool = False
    alerts_secret: bool = False
    private_vuln_reporting: bool = False
    auto_merge: bool = False
    merge_methods: tuple = ()
    topics: bool = False
    wiki: bool = False
    release_feed: bool = False
    dependabot: bool = False
    rulesets: bool = False
    pr_creation_cap: bool = False
    trusted_publishing: tuple = ()

    def has(self, name: str) -> bool:
        return bool(getattr(self, name, False))


class Provider:
    """The interface every hosting adapter implements. Methods a host cannot support raise Unsupported."""

    name = "base"

    def capabilities(self) -> Capabilities:
        raise NotImplementedError

    def whoami(self) -> str:
        """The logged-in account, or AuthMissing with the exact login command. Never runs a login."""
        raise NotImplementedError

    def list_repos(self, account: str, include_forks: bool, include_archived: bool, include_private: bool) -> list[Repo]:
        raise NotImplementedError

    def get_repo(self, repo: RepoId) -> Repo:
        raise NotImplementedError

    def repo_settings(self, repo: RepoId) -> dict:
        """Security features on or off, merge methods, wiki, PR creation cap, rulesets count."""
        raise NotImplementedError

    def tree(self, repo: RepoId, ref: str | None = None) -> list[str]:
        """Every file path at ref (default branch when None)."""
        raise NotImplementedError

    def file(self, repo: RepoId, path: str, ref: str | None = None) -> bytes | None:
        raise NotImplementedError

    def list_open_prs(self, repo: RepoId) -> list[PullRequest]:
        raise NotImplementedError

    def pr_detail(self, repo: RepoId, number: int) -> PullRequestDetail:
        raise NotImplementedError

    def pr_diff(self, repo: RepoId, number: int) -> str:
        raise NotImplementedError

    def checks_state(self, repo: RepoId, sha: str) -> ChecksState:
        raise NotImplementedError

    def author_history(self, repo: RepoId, login: str) -> AuthorHistory:
        raise NotImplementedError

    def usual_merge_method(self, repo: RepoId) -> str:
        """merge, squash or rebase: what recent merged PRs used, else the one method the repo allows."""
        raise NotImplementedError

    def release_published(self, repo_path: str, tag: str) -> str | None:
        """When a release or tag was published on this host (GitHub Actions versions live here)."""
        raise NotImplementedError

    def upsert_marked_comment(self, repo: RepoId, number: int, marker: str, body: str, apply: bool) -> Action:
        raise NotImplementedError

    def comment(self, repo: RepoId, number: int, body: str, apply: bool) -> Action:
        raise NotImplementedError

    def ensure_label(self, repo: RepoId, name: str, color: str, apply: bool) -> Action:
        raise NotImplementedError

    def add_labels(self, repo: RepoId, number: int, names: list[str], apply: bool) -> Action:
        raise NotImplementedError

    def escalate(self, repo: RepoId, number: int, to_user: str, authored_by_other: bool, apply: bool) -> list[Action]:
        raise NotImplementedError

    def merge(self, repo: RepoId, number: int, method: str, expected_head_sha: str, apply: bool) -> Action:
        raise NotImplementedError

    def close(self, repo: RepoId, number: int, comment: str, apply: bool) -> list[Action]:
        raise NotImplementedError

    def open_pr(self, repo: RepoId, head: str, base: str, title: str, body: str, labels: list[str], apply: bool) -> Action:
        raise NotImplementedError

    def alerts(self, repo: RepoId, kind: str) -> list[Alert]:
        raise NotImplementedError

    def enable(self, repo: RepoId, feature: str, apply: bool) -> Action:
        raise NotImplementedError

    def clone_url(self, repo: RepoId) -> str:
        raise NotImplementedError

    def wiki_exists(self, repo: RepoId) -> bool | None:
        raise NotImplementedError

    def run_logs(self, repo: RepoId, check_url: str) -> str:
        raise NotImplementedError

    def rate_state(self) -> dict:
        raise NotImplementedError


def as_dict(obj: Any) -> Any:
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if isinstance(obj, list):
        return [as_dict(o) for o in obj]
    return obj
