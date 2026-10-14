# Providers: the adapter interface, GitHub's capabilities, and the rule mapping

Read before touching hosting code, or when a repo's remote is not GitHub. Everything everkeep does on a host goes through one adapter; the skills and the decision rules never call `gh` or any host API directly. This build has one real adapter (GitHub) and a fake one for tests. Other hosts are designed for here and built later, one file each ([ai-docs/plans/providers-roadmap.md](../../../ai-docs/plans/providers-roadmap.md)). Research behind this page: [ai-docs/research/2026-10-13-other-providers.md](../../../ai-docs/research/2026-10-13-other-providers.md) and [ai-docs/research/2026-10-13-verification-and-recent-changes.md](../../../ai-docs/research/2026-10-13-verification-and-recent-changes.md), both read 2026-10-13.

## Repo identity

`<provider>:<path>`, for example `github:m4bwav/chartwright`, `gitlab:group/sub/project`, `codeberg:user/repo`, `bitbucket:workspace/repo`, `azure:org/project/repo`, and for a self-hosted instance `<provider>@<host>:<path>` (`gitea@git.example.com:user/repo`). The prefix may be dropped on the command line when it is unambiguous.

`registry.py` parses `git remote get-url origin` into an identity:

| Host | HTTPS | SSH | Path |
|---|---|---|---|
| GitHub | `https://github.com/{owner}/{repo}(.git)` | `git@github.com:{owner}/{repo}.git`, `ssh://git@github.com/{owner}/{repo}.git` | `owner/repo` |
| GitLab | `https://gitlab.com/{g1}/.../{project}(.git)` | `git@gitlab.com:{g1}/.../{project}.git`, `ssh://git@host[:port]/...` | full namespace, any depth (self-managed may sit under a subfolder) |
| Bitbucket Cloud | `https://[user@]bitbucket.org/{workspace}/{repo}(.git)` | `git@bitbucket.org:{workspace}/{repo}.git` | `workspace/repo` |
| Azure DevOps | `https://[org@]dev.azure.com/{org}/{project}/_git/{repo}`, `https://{org}.visualstudio.com/[DefaultCollection/]{project}/_git/{repo}` | `git@ssh.dev.azure.com:v3/{org}/{project}/{repo}`, `{org}@vs-ssh.visualstudio.com:v3/...` | `org/project/repo` (names may hold `%20`) |
| Forgejo, Gitea (Codeberg) | `https://codeberg.org/{owner}/{repo}(.git)` | `git@codeberg.org:{owner}/{repo}.git`, `ssh://git@host[:port]/...` | `owner/repo` |

Unknown host: the user's config may pin `host -> provider`. Without a pin the parser reports the host as unknown; a later adapter may probe (`/api/forgejo/v1/version` answers only on Forgejo, `/api/v1/version` on Gitea and Forgejo, `/api/v4/version` returns 401 JSON on GitLab).

**Unsupported in this build:** any identity whose provider is not `github` raises `ProviderNotSupported` with the message `provider <name> isn't supported yet (repo <id>); ask for it at https://github.com/m4bwav/everkeep/issues/new?template=provider.md`, and the command exits 3 having done nothing else.

## The interface (`scripts/everkeep/providers/base.py`)

Plain dataclasses in, plain dataclasses out; no host-specific field crosses the line. Every method that writes takes `apply: bool` and returns the action it took or would take, so dry runs and real runs share one path.

| Method | Returns | Notes |
|---|---|---|
| `capabilities()` | `Capabilities` | flags below; the duties ask before using a feature |
| `whoami()` | login, or an `AuthMissing` with the exact login command | never runs a login |
| `list_repos(account, include_forks, include_archived, include_private)` | `[Repo]` | `Repo`: id, default branch, visibility, fork, archived, pushed_at, topics, homepage, description |
| `repo_settings(repo)` | `RepoSettings` | security features on or off, merge methods allowed, PR controls, branch protection summary, Actions permissions |
| `list_open_prs(repo)` | `[PullRequest]` | number, title, author, author_kind (bot, member, outside), is_draft, head_sha, base, labels, created_at, url |
| `pr_detail(repo, n)` | `PullRequestDetail` | plus body, files with additions and deletions, linked issues, check summary; body and diff marked untrusted |
| `pr_diff(repo, n)` | text | untrusted |
| `checks_state(repo, sha)` | `ChecksState` | one of `passed`, `failed`, `not_run` (cancelled, skipped, no runner), `pending`, `none`, with the list of checks; each host's model reduces to these |
| `author_history(login)` | `AuthorHistory` | account age, PRs opened elsewhere in the last 7 days, prior PRs to this owner and their outcomes |
| `comment(repo, n, body, apply)` | `Action` | |
| `upsert_marked_comment(repo, n, marker, body, apply)` | `Action` | finds the authenticated user's comment holding `marker` and edits it, else creates one (verdict comments) |
| `ensure_label(repo, name, color, apply)` / `add_labels(repo, n, names, apply)` | `Action` | providers without labels degrade (see `escalate`) |
| `escalate(repo, n, to_user, reason, authored_by_other, apply)` | `[Action]` | each provider implements its own mapping (table below) |
| `merge(repo, n, method, expected_head_sha, apply)` | `Action` | always guarded by the head SHA the model judged |
| `close(repo, n, comment, apply)` | `[Action]` | |
| `push_branch_fix(...)` | not in the adapter | pushing is plain git on a worktree; the adapter only supplies the clone URL |
| `alerts(repo, kind)` | `[Alert]` or `Unsupported` | kinds: `dependency`, `code`, `secret` |
| `enable(repo, feature, apply)` | `Action` or `Unsupported` | features: `dependency_alerts`, `security_updates`, `secret_scanning`, `push_protection`, `private_vuln_reporting`, `code_scanning_default`, `pr_creation_cap` |
| `file(repo, path, ref)` | bytes or `None` | read a file without a clone |
| `clone_url(repo)` | URL | for throwaway clones |
| `run_logs(repo, check)` | text | failing check logs, for fixing bot PRs |

`Capabilities` flags: `labels`, `assignees`, `reviewers`, `issues`, `alerts_dependency`, `alerts_code`, `alerts_secret`, `private_vuln_reporting`, `auto_merge`, `merge_methods`, `topics`, `wiki`, `release_feed`, `dependabot`, `rulesets`, `pr_creation_cap`, `trusted_publishing` (which registries trust its CI).

When a flag is false the duty does not skip quietly: it records a "Not checked" line for the digest with the fallback it used (for example "no dependency alerts API on this host: ran osv-scanner on a clone instead").

## GitHub adapter (`github.py`): built in this build

Auth: whatever `gh auth status` reports; missing auth reports `gh auth login` for the user to run. All calls through `gh api` or `gh pr`; REST unless noted.

| Capability | Value | Call |
|---|---|---|
| list repos | yes | `gh repo list OWNER --json ...` (plus each configured org) |
| open PRs | yes | `gh pr list --json number,title,author,isDraft,headRefOid,labels,createdAt,url` |
| PR detail, files, linked issues | yes | `gh pr view N --json body,files,closingIssuesReferences,statusCheckRollup,...`; `author_association` from `GET /repos/{o}/{r}/pulls/{n}` (gh's JSON has no such field) |
| checks | yes | `statusCheckRollup` (CheckRun conclusion or StatusContext state), reduced to the five states |
| labels | yes | `gh label create`, `gh pr edit --add-label` |
| assignees, reviewers | yes | `gh pr edit --add-assignee`, `--add-reviewer` (GitHub refuses a review request from the PR's author: assign instead) |
| merge | yes | `PUT /repos/{o}/{r}/pulls/{n}/merge-async` with `sha` (GA 2026-10-01), poll; fallback `gh pr merge --match-head-commit SHA --squash|--merge|--rebase` |
| auto-merge | yes | not used by everkeep: it merges only what it judged, at the moment it judged it |
| close | yes | `gh pr close N --comment ...`; archiving a PR is UI-only (2026-10-08), so abuse archiving goes to Mark |
| dependency alerts | yes | `GET /repos/{o}/{r}/dependabot/alerts?state=open`; 410 Gone means withdrawn (since 2026-10-13) |
| code scanning alerts | yes | `GET /repos/{o}/{r}/code-scanning/alerts?state=open` |
| secret scanning alerts | yes | `GET /repos/{o}/{r}/secret-scanning/alerts?state=open` |
| enable dependency alerts / security updates | yes | `PUT /repos/{o}/{r}/vulnerability-alerts`, `PUT /repos/{o}/{r}/automated-security-fixes` |
| secret scanning, push protection | yes | `PATCH /repos/{o}/{r}` with `security_and_analysis` |
| private vulnerability reporting | yes | `PUT /repos/{o}/{r}/private-vulnerability-reporting` |
| CodeQL default setup | yes (free on public) | `PATCH /repos/{o}/{r}/code-scanning/default-setup` |
| open-PR cap for users without write access | yes | `PATCH /repos/{o}/{r}/interaction-limits/pulls/creation-cap` (`enabled`, `max_open_pull_requests`, `include_drafts`) |
| SHA pinning required | yes, per repo | Actions permissions `sha_pinning_required`; the `PUT` replaces the whole object, so read and send back every field |
| rulesets | yes | `GET/POST /repos/{o}/{r}/rulesets` (everkeep reads; creating one asks Mark, decision D11) |
| topics, wiki, release feed | yes | `gh repo edit --add-topic`; `.wiki.git`; `/{o}/{r}/releases.atom` |
| trusted publishing | npm, PyPI, NuGet, crates.io (GitHub-hosted runners; npm refuses self-hosted) | |
| rate limits | 5,000 REST an hour; content creation 80 a minute and 500 an hour; one write at a time, a second apart | headers `x-ratelimit-*`, `retry-after` |

## Fake adapter (`fake.py`)

In-memory repos, PRs, checks and alerts loaded from a JSON fixture; records every write. `tests/test_seam.py` runs `prs` classification, `gaps` and `report` through it with `gh` removed from PATH.

## Rule mapping (other providers: researched, not built)

| everkeep rule (GitHub) | GitLab (not built) | Bitbucket Cloud (not built) | Azure DevOps (not built) | Forgejo / Gitea (not built) |
|---|---|---|---|---|
| PR | merge request (`iid`) | pull request | pull request | pull request (also an issue number) |
| Escalate: assign + `needs-review` label (+ review request when someone else wrote it) | assignee + label (multiple assignees need Premium) | no labels, no assignees: add as reviewer, post a comment with a fixed marker, optionally prefix the title `[needs-review]` | add as required reviewer + PR label `needs-review` (no assignee field) | assignee + label (labels through the issues API) |
| Merge, guarded by head SHA | `PUT .../merge_requests/:iid/merge` with `sha` | `/mergeability/checks`, then `POST /merge` (async task) | PATCH `status=completed` with `lastMergeSourceCommit` | `POST /merge` with `head_commit_id` |
| Close | `state_event=close` | `POST /decline` | `status=abandoned` | PATCH `state=closed` |
| Checks state | `head_pipeline`, `detailed_merge_status` | `/statuses` + `/mergeability/checks` | PR statuses + policy evaluations | `/commits/{ref}/statuses` |
| Rulesets | protected branches + MR approval settings | branch restrictions | branch policies | branch protections |
| CI config (escalate on change) | `.gitlab-ci.yml` and its `include:` files | `bitbucket-pipelines.yml` | `azure-pipelines.yml` and templates (any path) | `.forgejo/workflows/`, `.gitea/workflows/`, `.github/workflows/`, `.woodpecker/`, `.woodpecker.y*ml` |
| Pinning rule | pin `include:` refs and images | pin `pipe:` versions and images | pin `resources.repositories` refs and task majors | pin `uses:` to SHAs, as on GitHub |
| Fork secret hygiene (never write the unsafe form) | protected variables; `ci_allow_fork_pipelines_to_run_in_parent_project=false` | secrets in secured or deployment variables (fork behaviour unverified) | "Make secrets available to builds of forks" off; org "securely build" on | no PR-head checkout in `pull_request_target`; Woodpecker: no `pull_request` event on secrets |
| Private vulnerability reporting | confidential issues + SECURITY.md pointing to them | SECURITY.md with an address (issues removed 2026-08-20) | SECURITY.md with an address | SECURITY.md with an address |
| Dependency alerts | Ultimate only: else osv-scanner on a clone | osv-scanner | GHAzDO if licensed, else osv-scanner | osv-scanner |
| Dependency bot | Renovate | Renovate | Renovate | Renovate |
| Topics | project topics | none | none | repo topics |
| Wiki | project wiki | none (removed 2026-08-20) | project or code wiki | repo wiki |
| Release feed | `/-/releases.atom`, `/-/tags?format=atom` | none | none | `/releases.atom`, `/tags.atom` |
| Trusted publishing | npm, PyPI, crates.io from gitlab.com only; NuGet | none | none | none |
| Spam lever | `merge_requests_access_level=private` | repo privacy, fork settings | members only by design | Actions approval for fork PRs; Codeberg's terms bar projects mostly written by AI tools, so everkeep's own changes there need care |
| Auth | `glab auth login` or `GITLAB_TOKEN` | Atlassian API token (app passwords are gone) | org-scoped PAT or Entra token (global PATs end 2026-12-01) | `tea auth login` / `GITEA_TOKEN`, or a token header |
| Rate limits | GitLab.com 2,000 a minute per user, notes 60 a minute | 1,000 an hour per user | 200 TSTU per sliding 5 minutes | none built in; Codeberg 2,000 per 10 minutes |

Related: builds on [ai-docs/plans/design.md](../../../ai-docs/plans/design.md) (section 5); see also [ai-docs/plans/providers-roadmap.md](../../../ai-docs/plans/providers-roadmap.md).
