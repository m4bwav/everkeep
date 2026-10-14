# Other git hosts for everkeep: GitLab, Bitbucket, Azure DevOps, Forgejo/Gitea

Phase 0 research, 2026-10-13. Scope: just enough about the four non-GitHub hosts to design everkeep's provider adapter interface so each can later be added as one adapter file. GitHub details live in the sibling research notes; the GitHub column here is only for comparison.

## Summary

All four hosts can do the core triage loop (list repos, list open change requests with diff and author, read check status, comment, merge, close, open one) over a REST API with a personal or scoped token, so one adapter interface can cover them. The differences that shape the interface are: Bitbucket Cloud has no labels, no assignees and (since 20 August 2026) no issues or wiki, so "escalate to Mark" must fall back to a reviewer plus a comment there; Azure DevOps has labels but no assignee (reviewers only, with votes) and calls closing "abandon" and merging "complete"; GitLab and Forgejo map almost one to one onto GitHub (labels, assignees, reviewers, auto-merge when checks pass). Security scanning is the weakest area: GitLab gives SAST free but dependency scanning, secret push protection and the vulnerability API only on Ultimate; Azure sells GitHub Advanced Security per committer; Bitbucket and Forgejo have nothing native. So everkeep's vulnerability step on non-GitHub hosts should run its own scanner (osv-scanner, or Renovate with `osvVulnerabilityAlerts`) rather than read a host alerts API. Renovate supports all four as first-class platforms; Dependabot exists only on GitHub. Trusted publishing: GitLab.com CI is accepted by npm, PyPI, NuGet and crates.io (self-managed GitLab is not, for npm, PyPI and crates.io); no registry accepts Bitbucket Pipelines, Azure Pipelines or Forgejo Actions. OpenSSF Scorecard supports GitHub and GitLab, and Azure DevOps only behind `SCORECARD_EXPERIMENTAL`. Codeberg's Terms of Use now bar projects that mostly consist of AI-generated code, which matters for any AI-written change everkeep proposes there.

## Capability matrix

| Capability | GitHub | GitLab | Bitbucket Cloud | Azure DevOps Services | Forgejo / Gitea (Codeberg) |
|---|---|---|---|---|---|
| Change request name | pull request | merge request (MR, `iid`) | pull request | pull request | pull request |
| Official CLI | `gh` | `glab` (JSON via `-F json`) | none official | `az repos` (azure-devops extension, JSON default) | `tea` (Gitea), `fj` (forgejo-cli); `berg` deprecated |
| List user/org repos | yes | yes (`/projects?membership=true`, `/groups/:id/projects`) | yes (`/repositories/{workspace}`, `/user/workspaces/.../permissions/repositories`) | yes (`_apis/git/repositories`, per org or project) | yes (`/user/repos`, `/orgs/{org}/repos`) |
| PR diff / changed files | yes | yes (`/diffs`; `/changes` deprecated) | yes (`/diff`, `/diffstat`, `/patch`) | yes (iterations and changes) | yes (`/pulls/{n}.diff`, `/pulls/{n}/files`) |
| Check status on PR | checks + statuses | `head_pipeline`, `detailed_merge_status` | `/pullrequests/{id}/statuses`, `/mergeability/checks` | PR statuses + policy evaluations | commit statuses (`/commits/{ref}/statuses`) |
| Labels on PRs | yes | yes (project and group labels) | no | yes ("labels", stored as tags) | yes (via issue labels API) |
| Assignees | yes | yes (multiple needs Premium) | no | no (reviewers only) | yes |
| Reviewers | yes | yes | yes | yes (required or optional, with votes) | yes (`requested_reviewers`) |
| Merge methods | merge, squash, rebase | merge, squash option, fast-forward (project setting) | merge_commit, squash, fast_forward, squash_fast_forward, rebase_fast_forward, rebase_merge | noFastForward, squash, rebase, rebaseMerge | merge, rebase, rebase-merge, squash, fast-forward-only, manually-merged |
| Auto-merge when checks pass | yes | yes (`auto_merge`) | partial: branch restriction `allow_auto_merge_when_builds_pass`, plus merge queues (Standard/Premium) | yes (auto-complete) | yes (`merge_when_checks_succeed`) |
| Close without merge | close | `state_event=close` | decline | abandon (`status=abandoned`) | `state=closed` |
| Branch protection API | rulesets, branch protection | protected branches (group-level and code owners need Premium) | branch restrictions | branch policies (`_apis/policy/configurations`) | branch protections |
| Dependency scanning | Dependabot alerts, free | Ultimate only | none native (Snyk app) | GHAzDO Code Security, paid | none |
| Secret scanning / push protection | free on public repos | push protection Ultimate (public-project rollout on GitLab.com not confirmed) | none native confirmed | GHAzDO Secret Protection, paid ($19/committer/month) | none |
| SAST | CodeQL, free on public | Free tier (basic analyzers, JSON report) | none native | GHAzDO Code Security, paid | none |
| Security alerts API | yes | Ultimate (REST being deprecated for GraphQL) | no | GHAzDO only | no |
| Private vuln reporting | yes (PVR, advisories) | confidential issues (all tiers) | none (issues removed) | none | none (email in SECURITY.md) |
| Dependency update bot | Dependabot + Renovate | Renovate (no Dependabot) | Renovate | Renovate (Dependabot only on GHAzDO roadmap, "Future") | Renovate (`forgejo`, `gitea` platforms) |
| CI file | `.github/workflows/*.yml` | `.gitlab-ci.yml` | `bitbucket-pipelines.yml` | `azure-pipelines.yml` (any path) | `.forgejo/workflows/`, `.gitea/workflows/`; Woodpecker `.woodpecker/` |
| Release/tag Atom feed | yes | yes (`/-/releases.atom`, `/-/tags?format=atom`) | no | no | yes (`/releases.atom`, `/tags.atom`, `.rss` too) |
| Scorecard | yes | yes (3 checks unsupported) | no | experimental only | no |
| Trusted publishing (npm/PyPI/NuGet/crates) | all four | all four (GitLab.com only for npm, PyPI, crates) | none | none | none |
| REST rate limit | 5,000/h per token | GitLab.com 2,000/min per user, 500/min unauth | 1,000/h per user (scales to 10,000), 60/h anon | 200 TSTU per sliding 5 min | none in software; Codeberg 2,000 per 600 s (header) |
| Restrict who opens PRs | yes (Feb and Jun 2026 settings) | `merge_requests_access_level=private` | private repos, fork settings | members only by design | Actions approval for fork PRs; no PR-creation limit found |

## GitLab (GitLab.com SaaS and self-managed)

**API and CLI.** REST v4 at `https://<host>/api/v4`. Auth header `PRIVATE-TOKEN: <token>` or `Authorization: Bearer`. Token types: personal, project and group access tokens (group tokens need an expiry date); CI jobs have `CI_JOB_TOKEN`. Pagination: `page`/`per_page` (max 100) with `Link`, `x-next-page`, `x-total`; keyset pagination for large collections; totals are omitted over 10,000 records. https://docs.gitlab.com/api/rest/ (read 2026-10-13)

- Repos: `GET /projects?membership=true` or `owned=true`; group projects via `/groups/:id/projects`. https://docs.gitlab.com/api/projects/ (read 2026-10-13)
- MRs: `GET /projects/:id/merge_requests?state=opened` (also per group and global). Fields `head_pipeline` (use instead of `pipeline`) and `detailed_merge_status` (values such as `mergeable`, `ci_must_pass`; replaces `merge_status`). Diffs: `/merge_requests/:iid/diffs` (`/changes` deprecated since 15.7, removal in API v5). Create: `POST` with `source_branch`, `target_branch`, `title`, optional `assignee_ids`, `reviewer_ids`, `labels`, `remove_source_branch`, `squash`. Update: `PUT` with `state_event=close|reopen`, `add_labels`, `remove_labels`, `assignee_ids`, `reviewer_ids`. Merge: `PUT /merge_requests/:iid/merge` with `auto_merge` (replaces deprecated `merge_when_pipeline_succeeds`), `sha` (must match source HEAD), `squash`, `should_remove_source_branch`. Comments are notes: `POST /merge_requests/:iid/notes`. https://docs.gitlab.com/api/merge_requests/ (read 2026-10-13)
- Protected branches: Free has allowed-to-merge, allowed-to-push-and-merge, allowed-to-force-push and wildcards; per-user/group entries, code owner approval, group-level protection and "who can unprotect" need Premium. The settings page is moving to **Settings > Repository > Branch rules**. API `/projects/:id/protected_branches`. https://docs.gitlab.com/user/project/repository/branches/protected/ (read 2026-10-13)
- CLI `glab` v1.123.0 (released 2026-10-13). `glab mr list -F json` (formats `text`, `json`), filters `--assignee`, `--reviewer`, `--label`, `--not-label`, `--draft`. Env vars: `GITLAB_TOKEN` (then `GITLAB_ACCESS_TOKEN`, `OAUTH_TOKEN`), `GITLAB_HOST` (then `GITLAB_URI`, `GL_HOST`), `GITLAB_API_HOST`, `GITLAB_SUBFOLDER`, `GITLAB_REPO`, `GLAB_ENABLE_CI_AUTOLOGIN`. `glab auth login` supports PAT and OAuth, keyring by default. Works on GitLab.com, Dedicated and Self-Managed. https://docs.gitlab.com/cli/mr/list/ and https://gitlab.com/gitlab-org/cli/-/raw/main/docs/source/configuration.md (read 2026-10-13)
- Rate limits (GitLab.com, current): authenticated API 2,000/min per user; unauthenticated 500/min per IP; `/api/v4/projects` list 2,000 per 10 min; `/api/v4/groups` list 50/min; note creation 60/min; pipeline creation 25/min per project/user/commit. A plan-based scheme is proposed (Free 5,000/h with 100/min burst; unauthenticated 60/h) but not yet in effect. Responses carry `ratelimit-*` headers (seen live: `ratelimit-name: throttle_unauthenticated_api`, limit 500). Self-managed limits are admin-set. https://docs.gitlab.com/user/gitlab_com/rate_limits/ (read 2026-10-13)

**Security by tier.** SAST: Free, Premium, Ultimate; Free gets open-source analyzers and a downloadable JSON report, Ultimate adds Advanced SAST, MR widget findings and vulnerability management. https://docs.gitlab.com/user/application_security/sast/ (read 2026-10-13). Dependency scanning: Ultimate. https://docs.gitlab.com/user/application_security/dependency_scanning/ (read 2026-10-13). Secret push protection: docs say Ultimate; GitLab MRs and issues from 2025 enable it by default for public projects on GitLab.com including Free, but the current docs page does not say so, so treat as unconfirmed. https://docs.gitlab.com/user/application_security/secret_detection/secret_push_protection/ and https://gitlab.com/gitlab-org/gitlab/-/merge_requests/207017 (read 2026-10-13). Vulnerabilities API: Ultimate, REST "in the process of being deprecated", use GraphQL. https://docs.gitlab.com/api/vulnerabilities/ (read 2026-10-13). Confidential issues: all tiers, visible to Planner role and above. https://docs.gitlab.com/user/project/issues/confidential_issues/ (read 2026-10-13). No GitHub-style private vulnerability reporting; a SECURITY.md is just a file.

**Renovate.** First-class `platform=gitlab`. Token needs Developer role at least, scope `api` (`read_api` for dry runs); Maintainer if only Maintainers may merge. Automerged MRs join merge trains when enabled. `automergeStrategy` is not implemented (always `auto`). Multiple assignees need Premium. Mend recommends its hosted app for GitLab.com. https://docs.renovatebot.com/modules/platform/gitlab/ (read 2026-10-13). No Dependabot. Community `dependabot-gitlab` exists (not checked).

**CI and fork MRs.** Config `.gitlab-ci.yml`. Default: a fork MR pipeline runs in the fork with the fork's CI config, resources and variables. A parent-project member can choose to run it in the parent, which uses the parent's variables; they must accept a warning first. Protected variables and protected runners are never available to fork MR pipelines. To forbid running fork pipelines in the parent, set the project attribute `ci_allow_fork_pipelines_to_run_in_parent_project=false` (Maintainer or admin). Safe default for everkeep to recommend: protect every secret variable, and set that attribute to false on public projects. https://docs.gitlab.com/ci/pipelines/merge_request_pipelines/ (read 2026-10-13)

**Spam controls.** No AI-spam feature found. Available levers: project attributes `merge_requests_access_level` and `forking_access_level` (`disabled`, `private` = members only, `enabled`). A proposal to require extra approvals for MRs with AI-authored commits is open, not shipped. https://docs.gitlab.com/api/projects/ and https://gitlab.com/gitlab-org/gitlab/-/work_items/578758 (read 2026-10-13)

**Feeds.** `https://gitlab.com/<full/path>/-/releases.atom` and `/-/tags?format=atom` both return Atom (tested 2026-10-13). `/-/tags.atom` redirects to sign-in.

## Bitbucket Cloud

**API.** REST 2.0 at `https://api.bitbucket.org/2.0`. Paths checked against the published spec `https://api.bitbucket.org/swagger.json` (downloaded 2026-10-13):

- Repos: `/repositories/{workspace}`, `/user/workspaces`, `/user/workspaces/{workspace}/permissions/repositories`.
- PRs: `/repositories/{workspace}/{repo_slug}/pullrequests` (GET with `state=OPEN`, POST to create); `/{id}` GET/PUT; `/diff`, `/diffstat`, `/patch`, `/commits`, `/conflicts`, `/comments`, `/tasks`, `/approve`, `/request-changes`, `/statuses`, `/mergeability/checks` (lists every merge check and whether it blocks), `/merge` (POST, optional `async`, then `/merge/task-status/{task_id}`), `/decline`. Workspace-wide `/workspaces/{workspace}/pullrequests/{selected_user}`.
- PR object fields: `id, title, summary, state (OPEN, MERGED, DECLINED, SUPERSEDED), author, source, destination, reviewers, participants, draft, queued, close_source_branch`. No `labels`, no `assignee`.
- Merge strategies: `merge_commit` (default), `squash`, `fast_forward`, `squash_fast_forward`, `rebase_fast_forward`, `rebase_merge`.
- Branch restrictions `/branch-restrictions`, kinds include `push`, `force`, `delete`, `restrict_merges`, `require_approvals_to_merge`, `require_passing_builds_to_merge`, `require_no_changes_requested`, `require_all_comments_resolved`, `enforce_merge_checks`, `allow_auto_merge_when_builds_pass`. Pipelines settings at `/pipelines_config` and `/pipelines_config/variables`.
- No `/issues` paths: Atlassian removed Bitbucket Issues and Wikis from UI and API on 20 August 2026. https://community.atlassian.com/forums/discussion/3193882/announcing-sunset-of-bitbucket-issues-and-wikis (read 2026-10-13)

**Auth.** App passwords: creation stopped 9 September 2025; Atlassian's phase 2 post says all were disabled 9 June 2026, a Bamboo KB says 28 July 2026; either way they are gone now. Use API tokens (scoped, with expiry) with basic auth as Atlassian account email plus token, or workspace/project/repository access tokens as Bearer. https://www.atlassian.com/blog/bitbucket/bitbucket-cloud-enters-phase-2-of-app-password-deprecation (read 2026-10-13). Renovate's Bitbucket token needs repository read/write, pull request read/write, user read, workspace read; username is the Atlassian email. https://docs.renovatebot.com/modules/platform/bitbucket/ (read 2026-10-13)

**CLI.** None official. Community `bitbottle` (Go, v1.52.0, May 2026) mimics `gh`; not evaluated. Plan on raw REST.

**Rate limits.** Anonymous 60/h; `/2.0/repositories/*` 1,000/h per user or token, scaling up to 10,000/h only for Standard/Premium workspaces with 100+ paid users using access tokens; webhooks 1,000/h; Git 60,000/h. 429 on excess. Headers `X-RateLimit-*` (seen live on an anonymous call: `X-Ratelimit-Limit: 60, 60;w=3600`). https://support.atlassian.com/bitbucket-cloud/docs/api-request-limits/ (read 2026-10-13)

**Security.** No native dependency, secret or code scanning found. Marketplace apps (Snyk, GitGuardian, Orca) and Pipelines pipes fill the gap; Code Insights reports (`/commit/{commit}/reports`) are where third-party scanners post results. No private vulnerability reporting, and with Issues gone, no confidential issues either.

**Renovate.** First-class `platform=bitbucket`. Not supported: assignees ("does not seem to be a Bitbucket concept"), `automergeStrategy=rebase`, collapsible Markdown, and anything that needs issues (Dependency Dashboard, config warnings). `platformAutomerge` is not offered for Bitbucket Cloud (the option lists Azure, Bitbucket Server, Forgejo, Gitea, GitHub, GitLab). Renovate `vulnerabilityAlerts` is GitHub-only. https://docs.renovatebot.com/configuration-options/ (read 2026-10-13). No Dependabot.

**CI and forks.** Config `bitbucket-pipelines.yml`. Secured variables are encrypted and masked. Atlassian's variables page does not say how pipelines treat PRs from forks; a third-party guide says secured repository variables are not available to fork PR pipelines. Not verified from a primary source. Merge queues are GA on Standard and Premium. https://www.atlassian.com/blog/bitbucket/unlocking-efficiency-with-merge-queues-in-bitbucket-cloud-now-ga (read 2026-10-13)

**Spam controls.** None specific found. Levers: repo privacy and fork settings.

**Feeds.** No release concept and no tag feed found (a `/rss` probe returned 404).

## Azure DevOps Services

**API and CLI.** REST at `https://dev.azure.com/{org}/{project}/_apis/...?api-version=7.1`.

- Repos: `GET _apis/git/repositories`. PRs: `GET _apis/git/repositories/{repo}/pullrequests?searchCriteria.status=active` (project-wide `_apis/git/pullrequests` also exists). Update via `PATCH .../pullrequests/{id}`: only `status`, `title`, `description`, `completionOptions`, `mergeOptions`, `autoCompleteSetBy.id` and `targetRefName` can change. Status values `active`, `abandoned`, `completed`. Merge = PATCH `status=completed` with `lastMergeSourceCommit`; auto-merge = set `autoCompleteSetBy` (auto-complete waits for all required policies). `completionOptions.mergeStrategy`: `noFastForward` (default), `squash`, `rebase`, `rebaseMerge`; also `deleteSourceBranch`, `bypassPolicy`, `transitionWorkItems`. PR object has `labels`, `reviewers` (with `vote` 10/5/0/-5/-10 and `isRequired`), `isDraft`, `forkSource`, `mergeStatus`, `createdBy`. No assignee field. https://learn.microsoft.com/en-us/rest/api/azure/devops/git/pull-requests/update?view=azure-devops-rest-7.1 (read 2026-10-13)
- CLI: `az repos pr create|list|show|update|set-vote|checkout`, `az repos pr reviewer add|list|remove`, `az repos pr policy list|queue`, `az repos pr work-item ...`. `create` takes `--auto-complete`, `--squash`, `--delete-source-branch`, `--draft`, `--labels`, `--required-reviewers`, `--optional-reviewers`; `update` takes `--status abandoned|active|completed`, `--auto-complete`, `--bypass-policy`. Output JSON by default (`-o json|jsonc|table|tsv|yaml|none`, `--query` JMESPath). Part of the azure-devops extension (Azure CLI 2.30+). https://learn.microsoft.com/en-us/cli/azure/repos/pr?view=azure-cli-latest (read 2026-10-13). PR comments are "threads" (REST, no `az repos pr` subcommand for them).
- Auth: PATs scoped to an organization (`vso.code_write` covers PR management) or Microsoft Entra tokens. Global (all-organization) PATs: creation blocked since 15 March 2026, all decommissioned 1 December 2026. https://devblogs.microsoft.com/devops/retirement-of-global-personal-access-tokens-in-azure-devops (read 2026-10-13). The CLI reads `AZURE_DEVOPS_EXT_PAT` or uses `az devops login` (from memory, not re-read). Renovate needs Code Read & Write, Work Items Read & Write for dashboards; Entra tokens last about an hour. https://docs.renovatebot.com/modules/platform/azure/ (read 2026-10-13)
- Rate limits: global 200 TSTUs per user in a sliding 5-minute window (one TSTU is a typical user's 5-minute load); the same 200 per pipeline. Delays up to 30 s, then 429 with `TF400733`. Headers `Retry-After`, `X-RateLimit-Resource`, `-Delay`, `-Limit`, `-Remaining`, `-Reset`, `-Cost`. https://learn.microsoft.com/en-us/azure/devops/integrate/concepts/rate-limits?view=azure-devops (read 2026-10-13)

**Security.** All paid. GitHub Advanced Security for Azure DevOps, sold as Secret Protection ($19 per active committer per month: push protection, secret scanning alerts) and Code Security ($30: dependency alerts, CodeQL, third-party findings), or the older bundle. Status checks `AdvancedSecurity/AllHighAndCritical` and `AdvancedSecurity/NewHighAndCritical` can gate PRs. Azure Repos only, Services only. https://learn.microsoft.com/en-us/azure/devops/repos/security/configure-github-advanced-security-features?view=azure-devops and https://devblogs.microsoft.com/devops/github-secret-protection-and-github-code-security-for-azure-devops/ (read 2026-10-13). No private vulnerability reporting.

**Renovate / Dependabot.** Renovate `platform=azure` is first-class; labels work (created automatically if the token can create tag definitions). Dependabot security updates for GHAzDO are listed on the Azure DevOps roadmap as "Future", not shipped. Community Dependabot extensions exist (not checked).

**CI and forks.** Config `azure-pipelines.yml` (any path; the pipeline points at it). The documented fork settings apply when Azure Pipelines builds GitHub repositories: **Build pull requests from forks of this repository** (on by default when a PR trigger is on), **Make secrets available to builds of forks** (off by default; leave off), **Make fork builds have the same permissions as regular builds** (off), **Require a team member's comment before building a pull request** (on all PRs, or only from non-team members). Org and project control **Limit building pull requests from forked GitHub repositories** with options disable, securely build (no secrets, no elevated token, comment-triggered only) or customize; on by default for organizations created since September 2023, off for older ones. https://learn.microsoft.com/en-us/azure/devops/pipelines/repos/github?view=azure-devops (read 2026-10-13). For Azure Repos forks (always inside the same organization) the behaviour was not checked.

**Spam controls.** Only organization members with Contribute permission can open PRs, so drive-by spam is structurally unlikely.

**Feeds.** No release concept and no tag feed.

## Forgejo and Gitea (Codeberg is Forgejo)

**Versions.** Codeberg runs Forgejo `16.0.0-dev` (reports `+gitea-1.22.0` for compatibility) from `/api/v1/version`; Forgejo also answers `/api/forgejo/v1/version`, Gitea does not (gitea.com returned 404 and `29.0.0+dev`). Gitea switched to major-number versions (latest release v28.1.0). Tested 2026-10-13.

**API.** `/api/v1`, OpenAPI at `/swagger.v1.json`. Auth `Authorization: token <t>` or `Bearer`, basic, or OAuth2. Pagination `page` and `limit` with `Link` and `x-total-count`; Codeberg max 50 per page, default 30 (`/api/v1/settings/api`). https://forgejo.org/docs/latest/user/api-usage/ (read 2026-10-13). From Codeberg's spec (downloaded 2026-10-13):

- Repos: `/user/repos`, `/orgs/{org}/repos`.
- PRs: `/repos/{owner}/{repo}/pulls` (GET `state=open`, POST create), `/pulls/{index}` (GET, PATCH: `state=closed`, `assignees`, `labels`), `/pulls/{index}.diff`, `/pulls/{index}/files`, `/commits`, `/reviews`, `/requested_reviewers`, `/update`, `/merge` (GET = is merged, POST, DELETE = cancel scheduled merge). Merge body `Do`: `merge`, `rebase`, `rebase-merge`, `squash`, `fast-forward-only`, `manually-merged`; plus `merge_when_checks_succeed`, `delete_branch_after_merge`, `head_commit_id`, `force_merge`.
- Labels and comments go through the issues API (a PR is an issue): `/issues/{index}/labels`, `/issues/{index}/comments`.
- Checks: `/commits/{ref}/statuses`, `/statuses/{sha}`. Branch protection: `/branch_protections`.
- Rate limits: none built in. Codeberg sends `ratelimit-policy: "baseline";q=2000;w=600`, that is 2,000 requests per 10 minutes (seen live on an anonymous call).

**CLIs.** `tea` (Gitea's, v0.16.0 on 2026-09-10; README describes a 1.0 that needs Gitea 28+), `--json` on `tea pr view`, token via `tea auth login --with-token` or `GITEA_TOKEN`, host via `TEA_HOST` or `GITEA_INSTANCE_URL`. https://gitea.com/gitea/tea (read 2026-10-13). `fj` forgejo-cli v0.6.0 (2026-07-19): create and merge PRs including AGit PRs, issues, releases; JSON output not documented. https://codeberg.org/forgejo-contrib/forgejo-cli (read 2026-10-13). `berg` (codeberg-cli) is deprecated in Homebrew in favour of forgejo-cli. Plan on raw REST.

**Security.** No native dependency, secret or code scanning; no security advisories, private vulnerability reporting or confidential issues found. Forgejo itself takes reports by encrypted email to security@forgejo.org. A SECURITY.md is just a file.

**Renovate.** First-class `platform=forgejo` and `platform=gitea`. Token scopes: `repo` read/write, `user` read, `issue` read/write, `organization` read (org labels and teams), `read:packages` if needed. Platform automerge needs Forgejo v10+ or Gitea v1.24+; merge style falls back to an allowed one. https://docs.renovatebot.com/modules/platform/forgejo/ and https://docs.renovatebot.com/modules/platform/gitea/ (read 2026-10-13). No Dependabot.

**CI and fork PRs.**
- Forgejo Actions: workflows in `.forgejo/workflows/` (Gitea uses `.gitea/workflows/`; both fall back to `.github/workflows/`, from memory, not re-read). For `pull_request` from a fork, "the secrets are not available and the automatic token only has read permissions". `pull_request_target` gets base-repo secrets and a write token and runs the default-branch workflow; docs advise never touching untrusted code there. https://forgejo.org/docs/latest/user/actions/reference/ (read 2026-10-13). Runs for PRs from forks, AGit PRs and authors with only read access wait for approval ("Approve once" or "Approve always"). https://forgejo.org/docs/latest/user/actions/security-pull-request/ (read 2026-10-13). Gitea: "To run actions for fork pull requests, approval is required." https://docs.gitea.com/usage/actions/faq (read 2026-10-13)
- Woodpecker (Codeberg's ci.codeberg.org, access by request): config `.woodpecker/*.yaml`, then `.woodpecker.yaml`, then `.woodpecker.yml`. Secrets are not exposed to `pull_request` events unless that event is enabled on the secret (keep it off for public repos). Project setting **Require approval for** defaults to approvals for forked repositories; **Allow pull requests** turns PR pipelines off entirely; **Trusted** is admin-only. https://woodpecker-ci.org/docs/usage/secrets and https://woodpecker-ci.org/docs/usage/project-settings (read 2026-10-13). Codeberg's hosted Forgejo Actions are "open alpha". https://docs.codeberg.org/ci/ (read 2026-10-13)

**Spam and AI policy.** Codeberg Terms of Use section 2(1) item 7: "You must not share projects that mostly consist of code written by 'generative AI'-tools (including services such as Claude, OpenAI Codex)". Violations lead to removal and a warning. https://codeberg.org/Codeberg/org/raw/branch/main/TermsOfUse.md (read 2026-10-13). The Forgejo project bans AI-generated contributions to Forgejo itself (March 2026 monthly report, secondary coverage). No per-repo "who can open PRs" setting found beyond disabling the pull request unit.

**Feeds.** `/{owner}/{repo}/releases.atom`, `/releases.rss`, `/tags.atom` all return feeds on Codeberg (tested 2026-10-13).

## OpenSSF Scorecard, osv-scanner, Renovate reach

Scorecard v5.6.0 (2026-10-12). GitHub (and GHES via `GH_HOST`) and GitLab (gitlab.com and self-managed, `GITLAB_AUTH_TOKEN`, `GL_HOST` for path-based hosts); on GitLab, Dangerous-Workflow, SAST and Token-Permissions are unsupported. Azure DevOps has a client (`clients/azuredevopsrepo`, `AZURE_DEVOPS_AUTH_TOKEN`, accepts `dev.azure.com/<org>/<project>/_git/<repo>` and `visualstudio.com` forms) but the CLI only tries it when `SCORECARD_EXPERIMENTAL` is set. Also a local-directory client. No Bitbucket or Forgejo. https://github.com/ossf/scorecard (README and `cmd/root.go`, read 2026-10-13)

osv-scanner is a standalone CLI over lockfiles, so it runs against any clone regardless of host. Renovate runs self-hosted on all four platforms; its `osvVulnerabilityAlerts` (experimental, default false) checks direct dependencies against OSV on any platform, while `vulnerabilityAlerts` reads GitHub alerts only. https://docs.renovatebot.com/configuration-options/ (read 2026-10-13)

## Trusted publishing (which CI counts)

| Registry | Accepted CI | Source |
|---|---|---|
| npm | GitHub Actions (GitHub-hosted runners), GitLab CI/CD (GitLab.com shared runners), CircleCI cloud. Self-hosted runners not yet. Provenance only from public repos, not CircleCI. | https://docs.npmjs.com/trusted-publishers (read 2026-10-13) |
| PyPI | GitHub Actions, GitLab CI/CD ("only projects hosted on https://gitlab.com"), Google Cloud, ActiveState. CircleCI per CircleCI docs, not on PyPI's page. Codeberg discussed, not accepted. | https://docs.pypi.org/trusted-publishers/adding-a-publisher/ (read 2026-10-13) |
| NuGet | GitHub Actions and GitLab CI/CD (`id_tokens` with `aud: https://www.nuget.org`, exchange at `/api/v2/token`; claims `namespace_path`, `project_path`). Self-managed GitLab not addressed. Azure Pipelines not listed. | https://learn.microsoft.com/en-us/nuget/nuget-org/trusted-publishing (read 2026-10-13) |
| crates.io | GitHub Actions; GitLab CI/CD since January 2026, "currently only works with GitLab.com". | https://blog.rust-lang.org/2026/01/21/crates-io-development-update (read 2026-10-13) |

No registry accepts Bitbucket Pipelines, Azure Pipelines, Forgejo Actions or Woodpecker. everkeep's "move to trusted publishing" rule should only fire for GitHub and gitlab.com repos.

## Repo identity: origin URL to provider:path

| Host | HTTPS | SSH | Path |
|---|---|---|---|
| GitHub | `https://github.com/{owner}/{repo}(.git)` | `git@github.com:{owner}/{repo}.git` | `owner/repo` |
| GitLab | `https://gitlab.com/{g1}/{g2}/.../{project}(.git)` | `git@gitlab.com:{g1}/.../{project}.git`, `ssh://git@host[:port]/{...}.git` | full namespace path, any depth; in web URLs `/-/` ends the project path. Self-managed may sit under a subfolder (`GITLAB_SUBFOLDER`), so depth cannot be inferred from the URL alone |
| Bitbucket Cloud | `https://bitbucket.org/{workspace}/{repo}(.git)`, `https://{user}@bitbucket.org/...` | `git@bitbucket.org:{workspace}/{repo}.git` | `workspace/repo_slug` |
| Azure DevOps | `https://dev.azure.com/{org}/{project}/_git/{repo}`, `https://{org}@dev.azure.com/{org}/{project}/_git/{repo}`, `https://{org}.visualstudio.com/[DefaultCollection/]{project}/_git/{repo}` | `git@ssh.dev.azure.com:v3/{org}/{project}/{repo}`, legacy `{org}@vs-ssh.visualstudio.com:v3/{org}/{project}/{repo}` | `org/project/repo`; project and repo names may contain URL-encoded spaces |
| Forgejo / Gitea | `https://codeberg.org/{owner}/{repo}(.git)` | `git@codeberg.org:{owner}/{repo}.git`, `ssh://git@host[:port]/{owner}/{repo}.git` | `owner/repo` (one level) |

Azure SSH forms from https://learn.microsoft.com/en-us/azure/devops/repos/git/use-ssh-keys-to-authenticate?view=azure-devops (read 2026-10-13; RSA keys only); visualstudio.com forms from Scorecard's parser. For unknown hostnames, detect the type by probing: `/api/forgejo/v1/version` answers only on Forgejo; `/api/v1/version` answers on Gitea and Forgejo; `/api/v4/version` returns 401 JSON on GitLab without a token (all tested 2026-10-13). Let a config file pin host to provider so probing is a fallback.

## Rule mapping

| everkeep rule (GitHub) | GitLab | Bitbucket Cloud | Azure DevOps | Forgejo / Gitea |
|---|---|---|---|---|
| PR | MR (`iid`) | PR | PR | PR (also an issue number) |
| Escalate: assign m4bwav + `needs-review` label | assignee + label (same) | no labels or assignees: add as reviewer and post a comment with a fixed marker string; optionally prefix title | add as required reviewer + PR label `needs-review` | assignee + label (same) |
| Merge own PR when checks pass | `PUT /merge` with `sha`, or `auto_merge=true` | `/mergeability/checks` then `POST /merge` | PATCH `status=completed` or set auto-complete | `POST /merge` with `head_commit_id` or `merge_when_checks_succeed` |
| Close stale / spam PR | `state_event=close` | `POST /decline` | `status=abandoned` | PATCH `state=closed` |
| Rulesets / branch protection | protected branches + MR approval settings | branch restrictions | branch policies (min reviewers, build validation, status checks) | branch protections |
| Workflow paths to pin and audit | `.gitlab-ci.yml` (+ `include:` files; pin `include:` refs and images) | `bitbucket-pipelines.yml` (pin `pipe:` versions and images) | `azure-pipelines.yml` and templates (pin `resources.repositories` refs and task major versions) | `.forgejo/workflows/`, `.gitea/workflows/`, `.github/workflows/`, `.woodpecker/` (pin `uses:` to SHAs as on GitHub) |
| Fork secret hygiene | protected variables; `ci_allow_fork_pipelines_to_run_in_parent_project=false` | keep secrets in secured or deployment variables (fork behaviour unverified) | keep "Make secrets available to builds of forks" off; org "securely build" control on | Actions: never check out PR code in `pull_request_target`; Woodpecker: no `pull_request` event on secrets |
| Private vulnerability reporting | confidential issues + SECURITY.md pointing to them | SECURITY.md with an email address | SECURITY.md with an email address | SECURITY.md with an email address |
| SECURITY.md | file only | file only | file only | file only |
| Topics | project topics | none found | none | repo topics |
| Wiki | project wiki (`.wiki.git`) | removed 20 Aug 2026 | project wiki or code wiki | repo wiki (`.wiki.git`) |
| Dependabot config | `renovate.json` instead | `renovate.json` | `renovate.json` | `renovate.json` |
| Vulnerability alerts | Ultimate API, else run osv-scanner | run osv-scanner | GHAzDO API if licensed, else osv-scanner | run osv-scanner |

Interface consequences: the adapter needs capability flags (`has_labels`, `has_assignees`, `has_issues`, `has_alerts_api`, `has_auto_merge`, `merge_methods`), an `escalate()` method each provider implements its own way, a `checks_state()` that normalises GitLab pipelines, Bitbucket statuses plus mergeability checks, Azure statuses plus policy evaluations, and Forgejo commit statuses into one pass/fail/pending value, and a `merge(sha_guard=...)` that always sends the head SHA it judged.

## Test approach for a later session

1. Disposable Forgejo (no account anywhere, nothing persisted):
   `docker run -d --name ek-forgejo -p 3000:3000 -p 2222:22 -e FORGEJO__security__INSTALL_LOCK=true codeberg.org/forgejo/forgejo:<current-major>`
   then `docker exec -u git ek-forgejo forgejo admin user create --admin --username ek --password <random> --email ek@example.invalid` and `forgejo admin user generate-access-token --username ek --scopes all`. Create a repo, a fork and a PR through the API, then exercise list, diff, label, assign, review request, comment, merge with `merge_when_checks_succeed`, close. Tear down with `docker rm -f ek-forgejo`. Gitea is the same with `docker.gitea.com/gitea:<version>` and `gitea admin user create`. Pin a current tag at the time; image names and the install-lock variable are from memory and need a check.
2. Read-only calls on public projects (verified anonymously 2026-10-13):
   - `curl "https://gitlab.com/api/v4/projects/gitlab-org%2Fcli/merge_requests?state=opened&per_page=1"` (returned 200 with `x-total`, `ratelimit-*`).
   - `curl "https://codeberg.org/api/v1/repos/forgejo/forgejo/pulls?state=open&limit=1"` (200, `Link`, `x-total-count`, `ratelimit-policy`).
   - Feeds: `https://gitlab.com/gitlab-org/cli/-/releases.atom`, `https://codeberg.org/forgejo/forgejo/releases.atom`.
   - Bitbucket anonymous is 60/h and needs a known public repo; find one first.
3. Azure DevOps needs a free organization; do not create one without Mark's go-ahead. Until then, test the Azure adapter against recorded fixtures built from the REST reference.
4. URL parser: table-driven unit tests from the identity table above, including nested GitLab groups, Azure `DefaultCollection`, `{org}@` prefixes, `vs-ssh`, ports in `ssh://` URLs, and percent-encoded spaces.

## Not verified

- Whether GitLab secret push protection is now on by default for Free public projects on GitLab.com (2025 MRs say yes, current docs say Ultimate).
- Bitbucket Pipelines behaviour for PRs from forks (whether they run in the parent and whether secured variables reach them); only a third-party source says secured variables are withheld.
- Bitbucket Cloud native auto-merge beyond the `allow_auto_merge_when_builds_pass` restriction kind and merge queues.
- Final cutoff date for Bitbucket app passwords (9 June vs 28 July 2026); both are past.
- Azure Repos (not GitHub) fork PR handling in Azure Pipelines.
- `AZURE_DEVOPS_EXT_PAT` env var name and `az devops login` (from memory).
- Gitea and Forgejo fallback to `.github/workflows/` (from memory).
- Whether Forgejo Actions issues OIDC tokens usable for any registry (none accepts it anyway).
- JSON output in `fj` and `berg`; `tea` output formats other than `--json` on `pr view`.
- GitLab `dependabot-gitlab` and Azure Dependabot community extensions: existence only, state not checked.
- Codeberg rate limit as documented policy (only observed from response headers).
- GitHub's 2026 PR access controls (Feb 13 and Jun 17 changelog entries) are from search results; the GitHub research note should confirm them.
- Forgejo and Gitea Docker image names and the admin CLI flags in the test recipe.
