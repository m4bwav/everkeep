"""In-memory adapter for tests: repos, PRs, checks, files and alerts from a JSON fixture; every write recorded.

tests/test_seam.py drives classification, gaps and the digest through it with gh removed from PATH, which proves
nothing above the interface depends on gh."""

from __future__ import annotations

import json
from pathlib import Path

from .base import (Action, Alert, AuthorHistory, Capabilities, ChecksState, FileChange, Provider, PullRequest,
                   PullRequestDetail, Repo, RepoId, Unsupported)
from .github import reduce_rollup


class FakeProvider(Provider):
    name = "github"

    def __init__(self, data: dict, base_dir: Path | None = None):
        self.data = data
        self.base_dir = base_dir or Path(".")
        self.writes: list[dict] = []
        self.repos = {r["id"]: r for r in data.get("repos", [])}

    @classmethod
    def from_file(cls, path: str | Path) -> "FakeProvider":
        p = Path(path)
        return cls(json.loads(p.read_text(encoding="utf-8")), p.parent)

    def _r(self, repo: RepoId) -> dict:
        try:
            return self.repos[str(repo)]
        except KeyError:
            raise Unsupported(f"fake: no repo {repo}")

    def _pr(self, repo: RepoId, number: int) -> dict:
        for p in self._r(repo).get("prs", []):
            if p["number"] == number:
                return p
        raise Unsupported(f"fake: no PR {repo}#{number}")

    def _write(self, kind: str, target: str, detail: str, apply: bool, **extra) -> Action:
        if apply:
            self.writes.append({"kind": kind, "target": target, "detail": detail, **extra})
        return Action(kind=kind, target=target, detail=detail, command=f"fake {kind} {target}", applied=apply)

    # reads
    def capabilities(self):
        caps = Capabilities(labels=True, assignees=True, reviewers=True, issues=True, alerts_dependency=True,
                            alerts_code=True, alerts_secret=True, private_vuln_reporting=True,
                            merge_methods=("merge", "squash", "rebase"), topics=True, wiki=True, dependabot=True,
                            rulesets=True, pr_creation_cap=True)
        for flag, value in (self.data.get("capabilities") or {}).items():
            setattr(caps, flag, value)
        return caps

    def whoami(self):
        return self.data.get("whoami", "owner")

    def _repo(self, r: dict) -> Repo:
        rid = r["id"].split(":", 1)[1]
        return Repo(id=RepoId("github", rid), default_branch=r.get("default_branch", "main"),
                    visibility=r.get("visibility", "public"), fork=r.get("fork", False), archived=r.get("archived", False),
                    pushed_at=r.get("pushed_at"), topics=r.get("topics", []), description=r.get("description", ""))

    def list_repos(self, account, include_forks, include_archived, include_private):
        out = []
        for r in self.repos.values():
            repo = self._repo(r)
            if repo.id.owner.lower() != account.lower():
                continue
            if (include_forks or not repo.fork) and (include_archived or not repo.archived) and \
                    (include_private or repo.visibility == "public"):
                out.append(repo)
        return out

    def get_repo(self, repo):
        return self._repo(self._r(repo))

    def repo_settings(self, repo):
        return dict(self._r(repo).get("settings", {}))

    def tree(self, repo, ref=None):
        r = self._r(repo)
        return list(r.get("tree") or r.get("files", {}).keys())

    def file(self, repo, path, ref=None):
        r = self._r(repo)
        files = (r.get("files_at", {}).get(ref) if ref else None) or r.get("files", {})
        v = files.get(path)
        return None if v is None else v.encode("utf-8")

    def _pull(self, repo: RepoId, p: dict) -> PullRequest:
        return PullRequest(repo=str(repo), number=p["number"], title=p.get("title", ""), author=p.get("author", "x"),
                           author_kind=p.get("author_kind", "bot"), is_draft=p.get("is_draft", False),
                           head_sha=p.get("head_sha", "0" * 40), head_ref=p.get("head_ref", ""), base=p.get("base", "main"),
                           labels=p.get("labels", []), created_at=p.get("created_at", ""), url=p.get("url", ""))

    def list_open_prs(self, repo):
        return [self._pull(repo, p) for p in self._r(repo).get("prs", []) if p.get("state", "open") == "open"]

    def pr_detail(self, repo, number):
        p = self._pr(repo, number)
        return PullRequestDetail(pr=self._pull(repo, p), body=p.get("body", ""),
                                 files=[FileChange(**f) for f in p.get("files", [])],
                                 linked_issues=p.get("linked_issues", []), checks=reduce_rollup(p.get("checks", [])),
                                 author_association=p.get("author_association", "NONE"),
                                 additions=sum(f.get("additions", 0) for f in p.get("files", [])),
                                 deletions=sum(f.get("deletions", 0) for f in p.get("files", [])))

    def pr_diff(self, repo, number):
        p = self._pr(repo, number)
        if "diff_file" in p:
            return (self.base_dir / p["diff_file"]).read_text(encoding="utf-8")
        return p.get("diff", "")

    def checks_state(self, repo, sha):
        for p in self._r(repo).get("prs", []):
            if p.get("head_sha") == sha:
                return reduce_rollup(p.get("checks_at_act", p.get("checks", [])))
        return ChecksState(state="none")

    def author_history(self, repo, login):
        h = (self.data.get("author_history") or {}).get(login)
        return AuthorHistory(login=login, **h) if h else AuthorHistory(login=login)

    def usual_merge_method(self, repo):
        return self._r(repo).get("merge_method", "squash")

    def release_published(self, repo_path, tag):
        return (self.data.get("releases") or {}).get(f"{repo_path}@{tag}")

    def alerts(self, repo, kind):
        a = self._r(repo).get("alerts", {})
        if kind not in a or a[kind] is None:
            raise Unsupported(f"{kind} alerts off for this repo")
        return [Alert(kind=kind, **x) for x in a[kind]]

    def clone_url(self, repo):
        return f"https://example.invalid/{repo.path}.git"

    def wiki_exists(self, repo):
        return self._r(repo).get("wiki")

    def run_logs(self, repo, check_url):
        return self.data.get("logs", {}).get(check_url, "")

    # writes
    def upsert_marked_comment(self, repo, number, marker, body, apply):
        p = self._pr(repo, number)
        comments = p.setdefault("comments", [])
        mine = [c for c in comments if c.get("user") == self.whoami() and marker in c.get("body", "")]
        if mine and mine[-1]["body"].strip() == body.strip():
            return Action(kind="verdict", target=f"{repo}#{number}", detail="comment already says this")
        detail = "edit verdict comment" if mine else "create verdict comment"
        if apply:
            if mine:
                mine[-1]["body"] = body
            else:
                comments.append({"user": self.whoami(), "body": body})
        return self._write("verdict", f"{repo}#{number}", detail, apply, body=body)

    def comment(self, repo, number, body, apply):
        if apply:
            self._pr(repo, number).setdefault("comments", []).append({"user": self.whoami(), "body": body})
        return self._write("comment", f"{repo}#{number}", "comment", apply, body=body)

    def ensure_label(self, repo, name, color, apply):
        labels = self._r(repo).setdefault("labels", [])
        if name in labels:
            return Action(kind="label", target=str(repo), detail=f"label {name} exists")
        if apply:
            labels.append(name)
        return self._write("label", str(repo), f"create label {name}", apply)

    def add_labels(self, repo, number, names, apply):
        if apply:
            self._pr(repo, number).setdefault("labels", []).extend(names)
        return self._write("label", f"{repo}#{number}", f"add {', '.join(names)}", apply)

    def escalate(self, repo, number, to_user, authored_by_other, apply):
        acts = [self.ensure_label(repo, "needs-review", "d93f0b", apply),
                self.add_labels(repo, number, ["needs-review"], apply),
                self._write("assign", f"{repo}#{number}", f"assign {to_user}", apply)]
        if authored_by_other:
            acts.append(self._write("review", f"{repo}#{number}", f"request review from {to_user}", apply))
        return acts

    def merge(self, repo, number, method, expected_head_sha, apply):
        p = self._pr(repo, number)
        a = self._write("merge", f"{repo}#{number}", f"{method} at {expected_head_sha[:12]}", apply)
        if apply:
            if p.get("head_sha") != expected_head_sha:
                a.ok, a.error = False, "head moved"
            else:
                p["state"] = "merged"
        return a

    def close(self, repo, number, comment, apply):
        acts = [self.comment(repo, number, comment, apply)]
        if apply:
            self._pr(repo, number)["state"] = "closed"
        acts.append(self._write("close", f"{repo}#{number}", "close", apply))
        return acts

    def enable(self, repo, feature, apply):
        if apply:
            self._r(repo).setdefault("settings", {})[feature] = True
        return self._write("enable", str(repo), f"switch on {feature}", apply)
