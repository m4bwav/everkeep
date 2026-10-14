"""GitHub adapter: every call through the gh CLI, so auth is whatever `gh auth login` holds and no token is stored.

Reads go one at a time; writes are spaced at least a second apart and capped per hour (GitHub's content-creation
limits are 80 a minute and 500 an hour, and its terms forbid automated excessive bulk activity)."""

from __future__ import annotations

import datetime as dt
import json
import re
import time

from ..util import EverkeepError, now, run, shell_line, which
from .base import (Action, Alert, AuthMissing, AuthorHistory, Capabilities, Check, ChecksState, FileChange, Provider,
                   PullRequest, PullRequestDetail, RateLimited, Repo, RepoId, Unsupported)

REPO_FIELDS = "name,nameWithOwner,isFork,isArchived,visibility,pushedAt,repositoryTopics,description,homepageUrl,defaultBranchRef"
PR_FIELDS = "number,title,author,isDraft,headRefOid,headRefName,baseRefName,labels,createdAt,url"


_ESC = chr(27)
_ESCAPES = re.compile(_ESC + r"\[[0-9;?]*[ -/]*[@-~]|" + _ESC + r"\][^" + chr(7) + "]*" + chr(7) + "?|" + _ESC + ".")


class NotFound(EverkeepError):
    pass


class Gone(EverkeepError):
    pass


def _norm_login(author: dict | None) -> tuple[str, bool]:
    author = author or {}
    login = author.get("login") or "ghost"
    is_bot = bool(author.get("is_bot")) or login.endswith("[bot]") or login.startswith("app/")
    if login.startswith("app/"):
        login = login[4:] + "[bot]"
    return login, is_bot


_FAILED = {"FAILURE", "TIMED_OUT", "ACTION_REQUIRED", "STARTUP_FAILURE", "ERROR"}
_NOT_RUN = {"CANCELLED", "STALE"}
_PASSED = {"SUCCESS", "NEUTRAL"}


def reduce_rollup(items: list[dict]) -> ChecksState:
    """Reduce GitHub check runs and commit statuses to passed, failed, not_run, pending or none.

    Skipped checks next to passing ones are normal (a deploy job that runs only on main); skipped or cancelled with
    nothing passing means CI did not run the change (a private repo whose self-hosted runner was offline)."""
    checks = []
    for it in items:
        name = it.get("name") or it.get("context") or "?"
        url = it.get("detailsUrl") or it.get("targetUrl") or it.get("html_url") or it.get("target_url") or ""
        if (it.get("__typename") == "StatusContext") or ("context" in it and "conclusion" not in it):
            st = (it.get("state") or "").upper()
            state = "passed" if st == "SUCCESS" else "failed" if st in _FAILED else "pending"
            raw = st
        else:
            status = (it.get("status") or "").upper()
            concl = (it.get("conclusion") or "").upper()
            raw = f"{status}/{concl}"
            if status != "COMPLETED":
                state = "pending"
            elif concl in _PASSED:
                state = "passed"
            elif concl in _FAILED:
                state = "failed"
            elif concl == "SKIPPED":
                state = "skipped"
            elif concl in _NOT_RUN:
                state = "not_run"
            else:
                state = "pending"
        checks.append(Check(name=name, state=state, url=url, raw=raw))
    states = {c.state for c in checks}
    if not checks:
        overall = "none"
    elif "failed" in states:
        overall = "failed"
    elif "pending" in states:
        overall = "pending"
    elif "not_run" in states:
        overall = "not_run"
    elif "passed" in states:
        overall = "passed"
    else:
        overall = "not_run"  # everything skipped
    for c in checks:
        if c.state == "skipped":
            c.state = "not_run"
    return ChecksState(state=overall, checks=checks)


class GitHubProvider(Provider):
    name = "github"

    def __init__(self, host: str | None = None, config: dict | None = None):
        self.host = host
        self.config = config or {}
        caps = (self.config.get("caps") or {})
        self.writes_per_hour = int(caps.get("writes_per_hour", 300))
        self._writes: list[float] = []
        self._last_write = 0.0
        self._me: str | None = None
        self.log: list[str] = []  # every command run, for the evidence section

    # ------------------------------------------------------------ plumbing

    def _r(self, repo: RepoId) -> str:
        return f"{self.host}/{repo.path}" if self.host else repo.path

    def _host_args(self) -> list[str]:
        return ["--hostname", self.host] if self.host else []

    def _gh(self, args: list[str], input_text: str | None = None, write: bool = False) -> str:
        if not which("gh"):
            raise AuthMissing("github", "install the GitHub CLI (https://cli.github.com), then run: gh auth login")
        if write:
            self._pace_write()
        self.log.append(shell_line(["gh", *args]))
        for attempt in range(3):
            p = run(["gh", *args], input_text=input_text, timeout=180)
            if p.returncode == 0:
                return p.stdout
            err = (p.stderr or p.stdout or "").strip()
            low = err.lower()
            if "rate limit" in low or "http 429" in low:
                if attempt < 2:
                    time.sleep(60 * (attempt + 1))
                    continue
                raise RateLimited(f"GitHub rate limit: {err[:200]}")
            if "http 404" in low or "not found" in low and "could not resolve" in low:
                raise NotFound(err[:300])
            if "http 410" in low:
                raise Gone(err[:300])
            if "gh auth login" in low or "not logged" in low or "authentication" in low and "http 401" in low:
                raise AuthMissing("github", "gh auth login" + (f" --hostname {self.host}" if self.host else ""), err[:200])
            raise EverkeepError(f"gh {' '.join(args[:3])} failed: {err[:400]}")
        raise EverkeepError("unreachable")

    def _pace_write(self) -> None:
        t = time.monotonic()
        self._writes = [w for w in self._writes if t - w < 3600]
        if len(self._writes) >= self.writes_per_hour:
            raise RateLimited(f"everkeep's own cap of {self.writes_per_hour} writes an hour reached; resume the run later")
        wait = 1.0 - (t - self._last_write)
        if wait > 0:
            time.sleep(wait)
        self._last_write = time.monotonic()
        self._writes.append(self._last_write)

    def api(self, path: str, method: str = "GET", body: dict | None = None, jq: str | None = None,
            paginate: bool = False, accept: str | None = None) -> object:
        args = ["api", *self._host_args(), "-X", method, path]
        if accept:
            args += ["-H", f"Accept: {accept}"]
        if paginate:
            args.append("--paginate")
        if jq:
            args += ["--jq", jq]
        if body is not None:
            args += ["--input", "-"]
        payload = json.dumps(body) if body is not None else None
        try:
            out = self._gh(args, input_text=payload, write=method != "GET")
        except EverkeepError as e:
            if "escape sequences" not in str(e):
                raise
            # gh 2.9x+ refuses to print a file holding terminal escapes; everkeep is no terminal, and strips them below.
            out = self._gh(args + ["--allow-escape-sequences"], input_text=payload, write=method != "GET")
        if accept and "raw" in accept:
            return _ESCAPES.sub("", out)
        if jq and jq.endswith("tojson"):
            return [json.loads(line) for line in out.splitlines() if line.strip()]
        out = out.strip()
        if not out:
            return None
        try:
            return json.loads(out)
        except json.JSONDecodeError:
            return out

    def _action(self, kind: str, target: str, detail: str, cmd: list[str], apply: bool, fn) -> Action:
        a = Action(kind=kind, target=target, detail=detail, command=shell_line(cmd), applied=False)
        if not apply:
            return a
        try:
            fn()
            a.applied = True
        except EverkeepError as e:
            a.ok, a.error = False, str(e)
        return a

    # ------------------------------------------------------------ reads

    def capabilities(self) -> Capabilities:
        return Capabilities(labels=True, assignees=True, reviewers=True, issues=True, alerts_dependency=True,
                            alerts_code=True, alerts_secret=True, private_vuln_reporting=True, auto_merge=True,
                            merge_methods=("merge", "squash", "rebase"), topics=True, wiki=True, release_feed=True,
                            dependabot=True, rulesets=True, pr_creation_cap=True,
                            trusted_publishing=("npm", "pypi", "nuget", "crates.io"))

    def whoami(self) -> str:
        if self._me is None:
            self._me = str(self.api("user", jq=".login")).strip()
        return self._me

    def _repo_from(self, d: dict) -> Repo:
        topics = [t.get("name") if isinstance(t, dict) else str(t) for t in (d.get("repositoryTopics") or [])]
        return Repo(id=RepoId("github", d["nameWithOwner"], self.host),
                    default_branch=((d.get("defaultBranchRef") or {}).get("name") or "main"),
                    visibility=(d.get("visibility") or "PUBLIC").lower(), fork=bool(d.get("isFork")),
                    archived=bool(d.get("isArchived")), pushed_at=d.get("pushedAt"), topics=topics,
                    description=d.get("description") or "", homepage=d.get("homepageUrl") or "")

    def list_repos(self, account, include_forks, include_archived, include_private):
        out = self._gh(["repo", "list", account, "--limit", "1000", "--json", REPO_FIELDS])
        repos = [self._repo_from(d) for d in json.loads(out or "[]")]
        return [r for r in repos if (include_forks or not r.fork) and (include_archived or not r.archived)
                and (include_private or r.visibility == "public")]

    def get_repo(self, repo):
        out = self._gh(["repo", "view", self._r(repo), "--json", REPO_FIELDS])
        return self._repo_from(json.loads(out))

    def _try(self, fn, default=None):
        try:
            return fn()
        except (RateLimited, AuthMissing):
            raise  # these stop the run cleanly; never read as "feature off"
        except EverkeepError:
            return default

    def repo_settings(self, repo):
        p = repo.path
        d = self.api(f"repos/{p}") or {}
        sa = d.get("security_and_analysis") or {}

        def status(key):
            v = (sa.get(key) or {}).get("status")
            return None if v is None else v == "enabled"

        def vuln_alerts():
            self.api(f"repos/{p}/vulnerability-alerts")
            return True
        return {
            "private": d.get("private"),
            "has_wiki": d.get("has_wiki"),
            "merge_methods": [m for m, k in (("merge", "allow_merge_commit"), ("squash", "allow_squash_merge"),
                                              ("rebase", "allow_rebase_merge")) if d.get(k)],
            "delete_branch_on_merge": d.get("delete_branch_on_merge"),
            "dependency_alerts": self._try(vuln_alerts, False),
            "security_updates": status("dependabot_security_updates"),
            "secret_scanning": status("secret_scanning"),
            "push_protection": status("secret_scanning_push_protection"),
            "private_vuln_reporting": self._try(lambda: (self.api(f"repos/{p}/private-vulnerability-reporting") or {}).get("enabled")),
            "code_scanning_default": self._try(lambda: (self.api(f"repos/{p}/code-scanning/default-setup") or {}).get("state")),
            "rulesets": self._try(lambda: len(self.api(f"repos/{p}/rulesets") or [])),
            "pr_creation_cap": self._try(lambda: self.api(f"repos/{p}/interaction-limits/pulls/creation-cap")),
        }

    def tree(self, repo, ref=None):
        res = self.api(f"repos/{repo.path}/git/trees/{ref or 'HEAD'}?recursive=1",
                       jq='.tree[] | select(.type=="blob") | .path | tojson')
        return list(res or [])

    def file(self, repo, path, ref=None):
        q = f"?ref={ref}" if ref else ""
        try:
            out = self.api(f"repos/{repo.path}/contents/{path}{q}", accept="application/vnd.github.raw")
        except (NotFound, Gone):
            return None
        return str(out).encode("utf-8")

    def _pr_from(self, repo: RepoId, d: dict) -> PullRequest:
        login, is_bot = _norm_login(d.get("author"))
        kind = "bot" if is_bot else ("owner" if login.lower() == self.whoami().lower() else "outside")
        return PullRequest(repo=str(repo), number=d["number"], title=d.get("title") or "", author=login,
                           author_kind=kind, is_draft=bool(d.get("isDraft")), head_sha=d.get("headRefOid") or "",
                           head_ref=d.get("headRefName") or "", base=d.get("baseRefName") or "",
                           labels=[l.get("name") for l in d.get("labels") or []], created_at=d.get("createdAt") or "",
                           url=d.get("url") or "")

    def list_open_prs(self, repo):
        out = self._gh(["pr", "list", "-R", self._r(repo), "--state", "open", "--limit", "200", "--json", PR_FIELDS])
        return [self._pr_from(repo, d) for d in json.loads(out or "[]")]

    def pr_detail(self, repo, number):
        fields = PR_FIELDS + ",body,files,closingIssuesReferences,statusCheckRollup,additions,deletions"
        d = json.loads(self._gh(["pr", "view", str(number), "-R", self._r(repo), "--json", fields]))
        pr = self._pr_from(repo, d)
        assoc = str(self._try(lambda: self.api(f"repos/{repo.path}/pulls/{number}", jq=".author_association"), "NONE")).strip()
        if pr.author_kind == "outside" and assoc in ("OWNER", "MEMBER", "COLLABORATOR"):
            pr.author_kind = "member"
        status_map = {"ADDED": "added", "DELETED": "deleted", "RENAMED": "renamed", "COPIED": "added"}
        files = [FileChange(path=f["path"], additions=f.get("additions", 0), deletions=f.get("deletions", 0),
                            status=status_map.get((f.get("changeType") or "").upper(), "modified"))
                 for f in d.get("files") or []]
        return PullRequestDetail(pr=pr, body=d.get("body") or "", files=files,
                                 linked_issues=[i.get("number") for i in d.get("closingIssuesReferences") or []],
                                 checks=reduce_rollup(d.get("statusCheckRollup") or []), author_association=assoc,
                                 additions=d.get("additions", 0), deletions=d.get("deletions", 0))

    def pr_diff(self, repo, number):
        return self._gh(["pr", "diff", str(number), "-R", self._r(repo)])

    def checks_state(self, repo, sha):
        runs = self.api(f"repos/{repo.path}/commits/{sha}/check-runs?per_page=100", jq=".check_runs[] | tojson") or []
        stats = self.api(f"repos/{repo.path}/commits/{sha}/status", jq=".statuses[] | tojson") or []
        items = [{"name": r.get("name"), "status": r.get("status"), "conclusion": r.get("conclusion"),
                  "detailsUrl": r.get("html_url")} for r in runs]
        items += [{"__typename": "StatusContext", "context": s.get("context"), "state": s.get("state"),
                   "targetUrl": s.get("target_url")} for s in stats]
        return reduce_rollup(items)

    def author_history(self, repo, login):
        if login.endswith("[bot]"):
            return AuthorHistory(login=login)
        created = self._try(lambda: str(self.api(f"users/{login}", jq=".created_at")).strip())
        since_day = (now() - dt.timedelta(days=7)).date().isoformat()

        def search(*extra):
            out = self._gh(["search", "prs", "--author", login, *extra, "--limit", "100", "--json", "repository"])
            return json.loads(out or "[]")
        recent = self._try(lambda: search("--created", f">={since_day}"), [])
        repos = {(r.get("repository") or {}).get("nameWithOwner") for r in recent}
        prior = {}
        for key, extra in (("merged", ["--merged"]), ("open", ["--state", "open"]), ("closed", ["--state", "closed"])):
            prior[key] = len(self._try(lambda: search("--owner", repo.owner, *extra), []))
        prior["closed_unmerged"] = max(0, prior.get("closed", 0) - prior.get("merged", 0))
        return AuthorHistory(login=login, account_created=created, repos_with_prs_last_7d=len(repos), prior_prs_here=prior)

    def usual_merge_method(self, repo):
        allowed = self.repo_settings_merge_methods(repo)
        if len(allowed) == 1:
            return allowed[0]
        merged = self._try(lambda: self.api(f"repos/{repo.path}/pulls?state=closed&per_page=20",
                                            jq='.[] | select(.merged_at != null) | .merge_commit_sha | tojson'), []) or []
        for sha in merged[:3]:
            parents = self._try(lambda: self.api(f"repos/{repo.path}/commits/{sha}", jq=".parents | length"))
            if parents is not None:
                guess = "merge" if int(parents) > 1 else "squash"
                if guess in allowed or not allowed:
                    return guess
        return "squash" if "squash" in allowed or not allowed else allowed[0]

    def repo_settings_merge_methods(self, repo) -> list[str]:
        d = self._try(lambda: self.api(f"repos/{repo.path}"), {}) or {}
        return [m for m, k in (("merge", "allow_merge_commit"), ("squash", "allow_squash_merge"),
                               ("rebase", "allow_rebase_merge")) if d.get(k)]

    def release_published(self, repo_path, tag):
        rel = self._try(lambda: self.api(f"repos/{repo_path}/releases/tags/{tag}", jq=".published_at"))
        if rel:
            return str(rel).strip()
        ref = self._try(lambda: self.api(f"repos/{repo_path}/git/ref/tags/{tag}", jq=".object"))
        if not isinstance(ref, dict):
            return None
        if ref.get("type") == "tag":
            return self._try(lambda: str(self.api(f"repos/{repo_path}/git/tags/{ref['sha']}", jq=".tagger.date")).strip())
        return self._try(lambda: str(self.api(f"repos/{repo_path}/commits/{ref['sha']}", jq=".commit.committer.date")).strip())

    def alerts(self, repo, kind):
        path = {"dependency": "dependabot/alerts", "code": "code-scanning/alerts", "secret": "secret-scanning/alerts"}[kind]
        try:
            items = self.api(f"repos/{repo.path}/{path}?state=open&per_page=100", paginate=True, jq=".[] | tojson") or []
        except EverkeepError as e:
            low = str(e).lower()
            if "no analysis" in low:
                raise Unsupported("code scanning is not set up on this repo")
            if isinstance(e, NotFound) or "403" in low or "disabled" in low:
                raise Unsupported(f"{kind} alerts are off for this repo, or this login cannot read them")
            raise
        out = []
        for a in items:
            if kind == "dependency":
                adv = a.get("security_advisory") or {}
                pkg = ((a.get("dependency") or {}).get("package") or {})
                vuln = (a.get("security_vulnerability") or {}).get("first_patched_version") or {}
                out.append(Alert(kind=kind, id=str(a.get("number")), severity=adv.get("severity", ""),
                                 package=pkg.get("name", ""), ecosystem=pkg.get("ecosystem", ""),
                                 summary=adv.get("summary", ""), url=a.get("html_url", ""),
                                 fixed_in=vuln.get("identifier", "") if isinstance(vuln, dict) else ""))
            elif kind == "code":
                rule = a.get("rule") or {}
                out.append(Alert(kind=kind, id=str(a.get("number")), severity=rule.get("security_severity_level") or rule.get("severity", ""),
                                 summary=rule.get("description", ""), url=a.get("html_url", "")))
            else:
                out.append(Alert(kind=kind, id=str(a.get("number")), severity="high",
                                 summary=a.get("secret_type_display_name") or a.get("secret_type", ""), url=a.get("html_url", "")))
        return out

    def clone_url(self, repo):
        return f"https://{self.host or 'github.com'}/{repo.path}.git"

    def wiki_exists(self, repo):
        p = run(["git", "ls-remote", f"https://{self.host or 'github.com'}/{repo.path}.wiki.git"], timeout=30,
                env=None)
        if p.returncode == 0:
            return bool(p.stdout.strip())
        if "not found" in (p.stderr or "").lower():
            return False
        return None

    def run_logs(self, repo, check_url):
        m = re.search(r"/actions/runs/(\d+)(?:/job/(\d+))?", check_url or "")
        if not m:
            raise Unsupported(f"no Actions run in {check_url}")
        args = ["run", "view", m.group(1), "-R", self._r(repo), "--log-failed"]
        if m.group(2):
            args[3:3] = ["--job", m.group(2)]
        out = self._gh(args)
        return "\n".join(out.splitlines()[-200:])

    def rate_state(self):
        core = self._try(lambda: self.api("rate_limit", jq=".resources.core"), {}) or {}
        return {"remaining": core.get("remaining"), "limit": core.get("limit"), "reset": core.get("reset"),
                "writes_this_hour": len(self._writes)}

    # ------------------------------------------------------------ writes

    def upsert_marked_comment(self, repo, number, marker, body, apply):
        me = self.whoami()
        comments = self.api(f"repos/{repo.path}/issues/{number}/comments?per_page=100", paginate=True,
                            jq=".[] | {id, user: .user.login, body} | tojson") or []
        mine = [c for c in comments if (c.get("user") or "").lower() == me.lower() and marker in (c.get("body") or "")]
        target = f"{repo}#{number}"
        if mine:
            cid = mine[-1]["id"]
            if (mine[-1].get("body") or "").strip() == body.strip():
                return Action(kind="verdict", target=target, detail=f"comment {cid} already says this", applied=False)
            return self._write("verdict", target, f"edit comment {cid}", "PATCH",
                               f"repos/{repo.path}/issues/comments/{cid}", {"body": body}, apply)
        return self._write("verdict", target, "create verdict comment", "POST",
                           f"repos/{repo.path}/issues/{number}/comments", {"body": body}, apply)

    def _write(self, kind: str, target, detail: str, method: str, path: str, body: dict | None, apply: bool) -> Action:
        """One REST write as an Action; the command shown is the gh api call it makes, body on stdin."""
        cmd = ["gh", "api", "-X", method, path] + (["--input", "-"] if body else [])
        return self._action(kind, str(target), detail, cmd, apply, lambda: self.api(path, method, body))

    def comment(self, repo, number, body, apply):
        return self._write("comment", f"{repo}#{number}", "comment", "POST", f"repos/{repo.path}/issues/{number}/comments",
                           {"body": body}, apply)

    def ensure_label(self, repo, name, color, apply):
        names = self._try(lambda: self.api(f"repos/{repo.path}/labels?per_page=100", paginate=True, jq=".[].name | tojson"), []) or []
        if name in names:
            return Action(kind="label", target=str(repo), detail=f"label {name} exists")
        return self._write("label", repo, f"create label {name}", "POST", f"repos/{repo.path}/labels",
                           {"name": name, "color": color, "description": "Waiting for the maintainer's review"}, apply)

    def add_labels(self, repo, number, names, apply):
        return self._write("label", f"{repo}#{number}", f"add {', '.join(names)}", "POST",
                           f"repos/{repo.path}/issues/{number}/labels", {"labels": names}, apply)

    def escalate(self, repo, number, to_user, authored_by_other, apply):
        t, base = f"{repo}#{number}", f"repos/{repo.path}"
        acts = [self.ensure_label(repo, "needs-review", "d93f0b", apply), self.add_labels(repo, number, ["needs-review"], apply),
                self._write("assign", t, f"assign {to_user}", "POST", f"{base}/issues/{number}/assignees",
                            {"assignees": [to_user]}, apply)]
        if authored_by_other:
            acts.append(self._write("review", t, f"request review from {to_user}", "POST",
                                    f"{base}/pulls/{number}/requested_reviewers", {"reviewers": [to_user]}, apply))
        return acts

    def merge(self, repo, number, method, expected_head_sha, apply):
        target = f"{repo}#{number}"
        cmd = ["gh", "api", "-X", "PUT", f"repos/{repo.path}/pulls/{number}/merge-async", "-f", f"sha={expected_head_sha}",
               "-f", f"merge_method={method}"]
        a = Action(kind="merge", target=target, detail=f"{method} at {expected_head_sha[:12]}", command=shell_line(cmd))
        if not apply:
            return a
        body = {"sha": expected_head_sha, "merge_method": method, "merge_action": "default"}
        try:
            res = self.api(f"repos/{repo.path}/pulls/{number}/merge-async", "PUT", body) or {}
        except NotFound:
            fallback = ["pr", "merge", str(number), "-R", self._r(repo), "--match-head-commit", expected_head_sha, f"--{method}"]
            a.command += "  (fallback: " + shell_line(["gh", *fallback]) + ")"
            try:
                self._gh(fallback, write=True)
                a.applied = True
            except EverkeepError as e:
                a.ok, a.error = False, str(e)
            return a
        except EverkeepError as e:
            a.ok, a.error = False, str(e)
            return a
        deadline = time.monotonic() + 90
        while isinstance(res, dict) and res.get("status") == "pending" and time.monotonic() < deadline:
            time.sleep(3)
            uuid = (res.get("details") or {}).get("uuid")
            if not uuid:
                break
            res = self._try(lambda: self.api(f"repos/{repo.path}/pulls/{number}/merge-async/{uuid}"), res)
        status = res.get("status") if isinstance(res, dict) else None
        a.applied = status in ("merged", "enqueued")
        a.ok = a.applied
        a.detail += f"; GitHub says {status}"
        if not a.ok:
            a.error = str((res or {}).get("details", {}).get("message", "merge did not complete") if isinstance(res, dict) else res)
        return a

    def close(self, repo, number, comment, apply):
        return [self.comment(repo, number, comment, apply),
                self._write("close", f"{repo}#{number}", "close", "PATCH", f"repos/{repo.path}/pulls/{number}",
                            {"state": "closed"}, apply)]

    def open_pr(self, repo, head, base, title, body, labels, apply):
        return self._write("open_pr", repo, f"{head} -> {base}", "POST", f"repos/{repo.path}/pulls",
                           {"title": title, "head": head, "base": base, "body": body}, apply)

    _ENABLE = {
        "dependency_alerts": ("PUT", "vulnerability-alerts", None),
        "security_updates": ("PUT", "automated-security-fixes", None),
        "secret_scanning": ("PATCH", "", {"security_and_analysis": {"secret_scanning": {"status": "enabled"}}}),
        "push_protection": ("PATCH", "", {"security_and_analysis": {"secret_scanning_push_protection": {"status": "enabled"}}}),
        "private_vuln_reporting": ("PUT", "private-vulnerability-reporting", None),
        "code_scanning_default": ("PATCH", "code-scanning/default-setup", {"state": "configured"}),
        "pr_creation_cap": ("PATCH", "interaction-limits/pulls/creation-cap",
                            {"enabled": True, "max_open_pull_requests": 1, "include_drafts": True}),
    }

    def enable(self, repo, feature, apply):
        if feature not in self._ENABLE:
            raise Unsupported(f"unknown feature {feature}")
        method, sub, body = self._ENABLE[feature]
        return self._write("enable", repo, f"switch on {feature}", method, f"repos/{repo.path}" + (f"/{sub}" if sub else ""),
                           body, apply)
