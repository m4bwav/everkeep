# everkeep design

## Status

Approved 2026-10-13 (decisions answered under section 12); Phase 2 build under way.

## Goal

an evergreen Claude Code plugin that maintains repositories and packages: by default the one repo you are in, on request a named or saved selection, or the whole account. GitHub only in this build, behind a provider interface that later takes GitLab, Forgejo/Gitea, Bitbucket and Azure DevOps as one adapter each.

## Next single action

Finish the Phase 2 build, then the Phase 3 dry runs (section 13); see ../HANDOFF.md.

Sources: the kickoff, the existing-work note and the landscape note (kept outside this repository), and this repo's research notes in [../research/](../research/): [live account snapshot](../research/2026-10-13-live-account-snapshot.md), [verification and recent changes](../research/2026-10-13-verification-and-recent-changes.md), [maintainer bots and practice](../research/2026-10-13-maintainer-bots-and-practice.md), [other providers](../research/2026-10-13-other-providers.md), [ecosystem APIs, scanners, EOL](../research/2026-10-13-ecosystem-apis-scanners-eol.md).

## 1. What it is, in one paragraph

A thin judgment layer over tools that already do most of the work. A stdlib Python CLI (`keep.py`) gathers facts and pre-classifies them: open PRs with checks, files, lockfile diffs, release ages and author history; alerts and scanner output; outdated packages and dead toolchains; missing modernization pieces; repos without a knowledge base. The model reads what the CLI hands it, makes the calls the rules leave to judgment (a human PR's merit, a failing bot PR's fix), and the CLI carries out the decisions with guards re-checked at the moment of acting. Everything is a dry run until `--apply`. Each run ends with one digest. Heavy work goes to the plugins that own it: package-modernize (rewrites, releases), everlast (knowledge bases), everscout (ecosystem watching), wikiwright (wikis), repo-traffic (download counts).

## 2. Scope: one repo by default

| Form | Means | Resolution |
|---|---|---|
| no scope | the repo in the current directory | `git remote get-url origin` parsed into `provider:path`; not a repo: the repo the user named; neither: ask |
| `--repo github:m4bwav/chartwright` (repeatable; `m4bwav/chartwright` or `chartwright` when unambiguous) | those repos | provider listing, exact match |
| `--select NAME` | a saved selection | the state store's `selections.json`; a selection stores its filter, not a frozen list, so new repos join it (with `--frozen` to store the list) |
| `--filter KEY=VALUE` (repeatable, ANDed) | a filtered set | keys: `provider`, `owner`, `ecosystem` (npm, nuget, pypi, openupm, plugin, none), `topic`, `name` (glob), `visibility`, `tier` (high, medium, low), `pushed` (`<90d`, `>365d`), `has` (open-prs, bot-prs, failing-prs, alerts, no-kb, gaps) |
| `--all` | every repo of every configured provider account | forks, archived and private excluded unless `--include-forks`, `--include-archived`, `--include-private` (Mark's overlay may set defaults: decision D4) |

`keep.py scope resolve [scope args]` prints the resolved list (repo id, tier, ecosystems, clone path) before anything acts; every other command takes the same arguments and prints the same list at the top of its output. `keep.py scope save NAME [scope args]` stores it.

Multi-repo runs go in risk order: low tier first, then medium, then high; within a tier, fewest open items first. A run is resumable: `keep.py run start` writes a run file listing every repo with status `pending`; each command marks `done`, `failed` or `skipped` with a reason; `keep.py run resume RUN_ID` carries on from the first `pending`. An interrupted run (context limit, rate limit, Ctrl+C) loses at most the repo in flight, and that repo's actions are idempotent (section 6). As in multi-gitter, turbolift and all-repos: the target list is frozen when the run starts, `run resume --failed` retries only the failures, and everkeep's own changes use one branch name per campaign (`everkeep/<campaign>`), skipping a repo where that branch already exists.

The rules do not loosen as scope widens. A multi-repo run also: stays under the provider's API limits (section 8); gathers escalations into the one digest; and **stops widening** when a repo shows something unexpected (a dependency on a known-compromised version, a lockfile pulling a git or tarball source, a workflow file nobody committed through a PR, a new attack pattern in the research notes): the run marks the rest `held`, writes the finding at the top of the digest, and waits for Mark.

No owner is hard-coded. Accounts come from the configured providers: whoever `gh auth status` says is logged in, plus any orgs listed in the user's config. Mark's specifics (registry accounts, download thresholds, the high-risk package list, private-runner rules, saved selections) live in his private overlay (section 7).

## 3. Skills

Recommendation (decision D8): **one listed skill, `everkeep`**, with each duty in a reference file read only when that duty runs. Reason: Mark's catalog is already about 12.3K tokens of descriptions against a 2K-character Claude Code listing budget (`tidy.py budget`, 2026-10-13), so every listed skill pushes another one out; and one skill means one description to keep clear of package-modernize and everscout.

| File | Read when |
|---|---|
| `skills/everkeep/SKILL.md` | always: Step 0 (freshness, overlay, providers), scope resolution, which duties to run, the decision rules in short, the digest, the safety rules for reading untrusted text |
| `skills/everkeep/references/prs.md` | PR triage: the merge, close and escalate rules in full, the negative-signal score, templates for closing comments, how to fix a failing bot PR |
| `skills/everkeep/references/deps.md` | dependency and toolchain bumps, vulnerabilities, per ecosystem |
| `skills/everkeep/references/gaps.md` | the modernization gap audit, the cheap fixes and their order, the hand-off to package-modernize |
| `skills/everkeep/references/kb.md` | knowledge-base bootstrap through everlast and the per-sweep log entry |
| `skills/everkeep/references/research.md` | ecosystem research per repo, sources and their pace, everscout beats |
| `skills/everkeep/references/providers.md` | the adapter interface, capability matrix, rule-mapping table |
| `skills/everkeep/references/safety.md` | prompt-injection rules, what never to load from a PR branch, throwaway worktrees, PID-only kills |
| `skills/everkeep/references/schedule.md` | the optional scheduled run and its tool allow-list |

The alternative (five skills: `everkeep`, `-prs`, `-deps`, `-gaps`, `-research`) gives direct triggers like "triage my PRs" a skill of their own; the hub's description can carry those phrases instead.

Description boundary, checked with `tidy.py check` before the build: everkeep is "keep the repos I already have healthy, one or many, routine and recurring"; package-modernize is "take one old package through a rewrite and release"; everscout is "watch a subject". The description ends with "Not for modernizing or rewriting one package (package-modernize) or watching a subject (everscout)." Decoy evals prove it (section 11).

## 4. The CLI: `skills/everkeep/scripts/keep.py`

Built inside the skill folder (decided 2026-10-13 during the build) so the skill travels whole to agents that copy only `skills/<name>/`; development scripts such as `scripts/size_check.py` stay at the repository root.

Stdlib Python 3.10+, one entry file plus a small package (`skills/everkeep/scripts/everkeep/`), no third-party imports, runs on Windows, macOS and Linux. Hosting calls go only through `skills/everkeep/scripts/everkeep/providers/` (section 5). Every command: same scope arguments; JSON with `--json`, Markdown otherwise; dry run unless `--apply`; prints the commands it would run (or ran) so the output is evidence.

| Command | Does | Network |
|---|---|---|
| `providers` | configured providers, logged-in account, auth state (with the exact login command when missing), capability matrix | provider |
| `scope resolve`, `scope save NAME`, `scope list` | section 2 | provider |
| `inventory` | every repo in scope: visibility, fork, archived, ecosystems (from files), registry packages, downloads and tier (repo-traffic data), local clone, `ai-docs/` present, vault registration | provider, disk |
| `prs` | every open PR: author and author history, files, size, labels, checks (green, failing, did not run, pending), head SHA, for bot PRs the package, from and to versions, release age, publisher continuity, lockfile diff summary; a pre-classification with reasons | provider, registries |
| `prs show REPO#N` | one PR's full diff and facts for the model to read, untrusted text fenced | provider |
| `deps` | outdated direct dependencies and toolchains (Node, .NET SDK and TFMs, Python, Unity, Actions runtimes) per ecosystem, with release age and major or minor; publish times from the registry's full document (npm `time` and `_npmUser`, with `trustedPublisher` and `approver` compared across versions; NuGet registration `published` and search `owners`; PyPI `upload_time`; OpenUPM's npm-format `time`) | registries, endoflife.date API v1 |
| `vulns` | provider alerts (Dependabot, code scanning, secret scanning) plus the provider-neutral scanners on a clone: `osv-scanner scan source -r --format json` (v2.7.0; exit 128 means nothing to scan, not a failure), `npm audit --json` and `npm audit signatures` (exit 1 means findings), `dotnet package list --vulnerable --include-transitive --format json` (exits 0 with findings: parse it), `pip-audit -f json` (top level `{"dependencies","fixes"}`). A missing scanner is reported with its install line (`winget install Google.OSVScanner`), never skipped silently | provider, local tools |
| `gaps` | the modernization gap table per repo (section 9) | provider, disk |
| `kb` | repos with no `ai-docs/` or not registered in the vault; prints the everlast commands | disk |
| `research gather REPO` | facts for an ecosystem note: dependents, competing packages, trends, upcoming deprecations (ecosyste.ms, deps.dev, HN Algolia, release feeds) | public APIs |
| `act PLAN.json` | carries out the model's decisions (merge, close, comment, label, assign, request review, enable a setting, open a PR); re-checks each guard first; refuses anything the rules forbid | provider |
| `run start / resume / status` | the resumable multi-repo run (section 2) | none |
| `report RUN_ID` | the digest (section 10) | none |
| `state show REPO`, `state forget REPO` | per-repo memory | none |

`act` is the only command that writes, and only with `--apply`. Its guards, checked at the moment of acting, not at classification:
- merge: through the adapter's merge call, which on GitHub uses the asynchronous merge endpoint GitHub now recommends (`PUT /repos/{o}/{r}/pulls/{n}/merge-async` with the expected head `sha`, then polling the returned id; GA 2026-10-01) and falls back to `gh pr merge --match-head-commit SHA`; either way the head must be the one the model reviewed, so a push after review refuses the merge; checks green and actually run on that SHA, PR not draft, the rule that allowed it still holds, the repo's usual merge method (read from recent merged PRs, falling back to the repo's allowed methods);
- close: a templated comment from `templates/comments/`, never free text from the PR itself;
- escalate: assignee plus `needs-review` label (created if missing), plus a review request when someone else authored it, plus the verdict comment saying why;
- verdict comment: found by its hidden marker among the PR's comments by the authenticated user and edited in place, created only when none exists (section 6);
- never: tag, publish, approve a deployment, delete a branch or repo, change a ruleset, or edit a workflow file without the rule that allows it.

Shared code it calls instead of copying: package-modernize's `survey-github.sh`, `topics.py`, `lint-workflows.sh`, `nuget-latest.py`, `check-readme-images.mjs`, found through the installed skill (`~/.claude/skills/package-modernize` or `PACKAGE_MODERNIZE_HOME`); when it is absent, the gap checks that need it are reported as "not checked: package-modernize not installed" (never silently skipped). everlast's `everlast.py` the same way.

## 5. Provider layer

`skills/everkeep/scripts/everkeep/providers/base.py` defines the interface as an abstract class and plain dataclasses (`Repo`, `PullRequest`, `Check`, `Alert`, `Capabilities`). `github.py` implements it with the `gh` CLI (`gh api`, `gh pr`), so auth is whatever `gh auth login` holds and no token is stored. `fake.py` is an in-memory adapter for tests. `registry.py` maps a remote URL to a provider: github.com and configured GitHub Enterprise hosts go to `github`; a recognised but unbuilt host (gitlab.com, codeberg.org, bitbucket.org, dev.azure.com, a configured self-hosted host) raises `ProviderNotSupported` whose message is "provider X isn't supported yet; ask for it at https://github.com/m4bwav/everkeep/issues/new?template=provider.md", and the command exits 3 having done nothing else.

Repo identity is provider-qualified: `github:m4bwav/chartwright`, `gitlab:group/sub/project`, `codeberg:user/repo`, `gitea@<host>:user/repo`. The interface, the GitHub capability matrix and the rule-mapping table with every provider's column are in [../../skills/everkeep/references/providers.md](../../skills/everkeep/references/providers.md) (written in this phase); the roadmap for the next adapters is [providers-roadmap.md](providers-roadmap.md).

Capability gaps degrade openly: each duty asks `caps.has("labels")` and the like, and anything missing becomes a line in the digest's "Not checked" section with the provider-neutral fallback used. The test `tests/test_seam.py` runs `prs` classification, `gaps` and `report` entirely through the fake adapter with `gh` removed from PATH, proving nothing above the interface depends on `gh`.

## 6. Decision rules, as the CLI applies them

The rules are the kickoff's, unchanged; the CLI encodes the mechanical half and leaves the rest to the model with a reason attached.

**Repo tier** (decision D6): `high` = a package people download (overlay list: RandomNameGeneratorLibrary, JsonPrettyPrinter; plus anything over the overlay's thresholds in repo-traffic's data); `shared` = someone else's repo, a fork, or one with other committers or collaborators; `medium` = any other repo that publishes to a registry; `low` = everything else. In `high` and `shared` repos, every change that is not docs-only escalates, whatever else holds.

**Pre-classification of a PR** (first matching row wins):

| Class | When |
|---|---|
| `hold` | checks pending, or the bot version is younger than the cooldown (3 days; 7 for a major; security updates exempt from the wait, not from green CI). The age comes from the registry's own publish time for that version, never from the bot's or the package manager's setting: Renovate skipped its age gate on digest updates (CVE-2026-88884, fixed in 44.3.1) and pnpm 10.14 ignored a repo's `minimum-release-age`, letting a 77-minute-old malicious TanStack version in (Nx Console incident) |
| `fix` | a bot PR whose checks failed, or did not run (cancelled, skipped, runner offline): the model diagnoses (logs through the provider), fixes in a throwaway worktree, pushes to the PR branch, and the PR returns to `hold` |
| `escalate` | repo tier `high` or `shared`; a major or breaking bump; a public API change; touches CI or publish config, `package.json` scripts, `.mcp.json`, `.claude/`, `.vscode/`, secrets, permissions, settings (except the narrow pin exception, decision D7); deletes data; checks failed and could not be fixed; lockfile diff shows a new transitive package with a danger signal (D14), a git, tarball or URL source, a registry change, a new maintainer or publisher, a new install script or `binding.gyp`, or **removed target sections** (the Dependabot NuGet case in the live snapshot); a new version whose source repository gained commits from look-alike bot authors (IronWorm forged Claude's GitHub noreply address); the model is unsure. Valid provenance never clears any of these: TanStack, Miasma and IronWorm all published through the victim's own OIDC pipeline with genuine attestations |
| `close-candidate` | a human PR whose negative-signal score passes the threshold (section 6a); the model confirms by reading the whole diff |
| `merge-candidate` | bot PR: green on the head SHA, past the cooldown, same publisher, clean lockfile diff; human PR: small, wanted (linked to an accepted issue or a clear bug), whole diff read, touches no executed config; docs-only PR from anyone with green checks |

The model can move a PR toward `escalate` freely and never toward `merge` against the table. Also automatic: closing a bot PR that a newer bot PR for the same dependency has superseded.

**Judging and acting are separate** ([maintainer bots and practice](../research/2026-10-13-maintainer-bots-and-practice.md): every 2026 incident, Clinejection, TrustIssues and GitLost, came from an agent that read hostile text and held write tools in the same context). The judging pass reads and returns a verdict per item in `PLAN.json`; only `keep.py act` writes, and only allowlisted actions. In a multi-repo run each repo is judged in its own fresh subagent context that holds only that repo's facts, so text from one repo never sits beside another repo's content or a public comment to write (GitLost leaked a private README that way). Public comments come from templates with slots for facts, never free text.

**Caps** (starting values, in the overlay; raised once learning mode shows they are safe): at most 3 merges per repo and 10 per run, 5 closes per run, one verdict comment per PR, never a second reply to the same person, at most 2 open everkeep PRs per repo (the dotnet team measured 5 to 9 hours of review for 9 agent PRs). A new rule runs in learning mode for at least one sweep before it acts.

**Verdict comments** (Mark, 2026-10-13: "warn me not to merge a dependency until x time ... and leave a comment on it"). Every PR everkeep holds, escalates or plans to close gets one everkeep comment saying what it decided, why, and when that changes, for example "Holding until 2026-10-16: NUnit3TestAdapter 6.3.1 was published 2026-10-12 and the cooldown is 3 days. If checks stay green, everkeep merges it on the first run after that date. Merge it sooner by hand if you need it." The comment is sticky: it carries a hidden marker (`<!-- everkeep:verdict -->`) and later runs edit it in place, never stack new ones. When the verdict changes (cooldown passed, checks went red, escalated), the edit says so with the date. Merged and closed PRs keep the last verdict as their record.

**Learning mode** (the account-wide shakedown, decision D13): `--learn` (the overlay can make it the default) runs every duty and posts the verdict comment on each PR, but takes no other action: no merges, closes, pushes or settings. Each verdict ends with "everkeep is in learning mode; reply on this PR or tell the agent if this call is wrong." Mark's corrections go to the skill's LEARNINGS.md and, when they change a rule, to the rules and their tests. The point is to meet the real mess across all the repos with every call visible and reversible before any of them acts.

**6a. Negative-signal score** (each signal a weight, never one as proof): no linked or accepted issue; unrequested refactor or cosmetic churn; first-time author with a burst of PRs across many repos the same week; description that restates the diff; calls to APIs that do not exist (the model checks); new or renamed dependencies (slopsquatting: the name is checked on the registry, with its age and downloads); tests mocked so they cannot fail; spam or Hacktoberfest padding; touching executed config. The signals follow GitHub Next's contribution checklist (on topic per CONTRIBUTING.md, followed the process, focused, new dependency, tests, description, size) plus account signals. A close needs four or more failing, at least one about the content, an author who is not a collaborator, no linked issue, and the model's own read. Signals that produced false positives in anti-slop's tracker are not used: digits in a username, URLs counted as code references, "Update branch" commits made by a maintainer. A close never calls the PR AI-made. Abuse is closed through the API and the archive step goes to Mark (archiving is UI-only). The closing comment comes from a template and is posted with Mark's login, so he can reopen it: thanks, the written rule it falls under (CONTRIBUTING.md or the AI policy), what would be welcome. If the author replies with hostility, everkeep stops replying and escalates.

**Fixing a failing bot PR**: the PR branch is checked out into a throwaway worktree with no credentials beyond the push the fix needs; nothing from the branch's `.mcp.json`, `.claude/`, `.vscode/` or AGENTS.md is loaded; the fix is the smallest mechanical one (regenerate a lockfile on the right OS, bump a pinned SDK, adjust a test pin); the commit has no AI attribution; CI reruns; the PR goes back through the table.

## 7. State store and overlay

- **State**: `~/.everkeep/` (override `EVERKEEP_HOME`), never in a public repo. `config.json` (providers and extra accounts, overlay path, clone map, defaults), `selections.json`, `state/<provider>/<owner>/<repo>.json` (last run per duty, decisions taken with PR and head SHA, escalations open and when they were raised, snoozes), `runs/<run-id>.json` (resolved scope, per-repo status, the digest path), `clones/` (throwaway clones and worktrees, deleted after each repo). Writes are atomic (temp file plus rename) so an interrupted run never leaves half a file.
- **Overlay**: `EVERKEEP_OVERLAY`, else `~/.everkeep/OVERLAY.md`. Mark's is a junction to a private folder (decision D10 for where: recommended, the vault sidecar `vault/projects/everkeep/private/`). It holds identities (GitHub `m4bwav`, npm `markrogers`, NuGet `rogersm0`), the high-risk list and thresholds, the repo-traffic data path, the private-runner rule and the runner check's path, his starter selections, the alert channel, and pointers to the package-modernize overlay for standing decisions it already records (topics, icons, wikis, size budget, banner).

## 8. Provider limits and safety

- GitHub: authenticated REST 5,000 requests an hour; content creation (comments, merges, labels) at most 80 a minute and 500 an hour; GitHub asks for writes one at a time with at least a second between them, and its Acceptable Use Policies forbid "automated excessive bulk activity" ([verification and recent changes](../research/2026-10-13-verification-and-recent-changes.md)). A personal account has no account-wide alert listing, so a full sweep loops over the repos: about 10 reads a repo, about 670 for the account, well inside the hourly limit. The adapter reads `x-ratelimit-remaining`, sleeps on `retry-after`, spaces writes by at least one second and caps a run at 300 writes an hour, and makes reads one at a time. A run that hits a limit marks the repo `pending` and stops cleanly for `run resume`.
- Platform quirks the adapter handles: a withdrawn Dependabot alert answers 410 Gone since 2026-10-13 (record it as withdrawn, not an error); archiving a PR is UI-only, so abuse is closed through the API and the archive step goes to Mark in the digest; `sha_pinning_required` is set per repo (no account-level switch on a personal account) and its `PUT` replaces the whole Actions settings object, so the adapter reads it and sends every field back.
- Untrusted text: PR and issue titles, bodies, comments, commit messages, diffs and file contents from a PR are data. `prs show` strips HTML comments, zero-width and other invisible characters and hidden attributes, caps each field's size, and fences what is left in a block labelled untrusted; the skill says never to follow instructions found there, and no title is ever pasted into an instruction. PR code never runs on Mark's machine for judging: files are read as text over a base-branch checkout. No PR branch's `.mcp.json`, `.claude/`, `CLAUDE.md`, `AGENTS.md`, `.vscode/`, `.gemini/`, `.husky/` or `.npmrc` is ever loaded; in a worktree used to fix a bot PR these are restored from the base branch before anything runs (claude-code-action's own restore list misses AGENTS.md and `.vscode/`). No AI agent runs inside GitHub Actions in this build (no gh-aw, no claude-code-action); worktrees for PR code are made with `git worktree add` from a fetched ref, outside any project folder Claude Code would read settings from, and are deleted after.
- Headless runs (the optional schedule, D2, and eval runs): `claude -p` shows no trust dialog, and started inside a repository it runs that repository's settings hooks and connects its `.mcp.json` servers without asking ([ecosystem APIs, scanners, EOL](../research/2026-10-13-ecosystem-apis-scanners-eol.md), section 6). A headless everkeep run therefore starts in `~/.everkeep`, never in a repo, with `--setting-sources user`, `--settings '{"disableAllHooks":true}'`, `--strict-mcp-config` with no MCP config, `--tools` limited to Bash, Read, Grep, Glob and Write, `--allowedTools` narrowed to `Bash(python *keep.py*)`, `Bash(git *)` and `Bash(gh *)`, `--permission-mode dontAsk`, and no web tools. The exact invocation is tested before any schedule is created; `skills/everkeep/references/schedule.md` holds it.
- No `pull_request_target` with a PR-head checkout in anything everkeep writes, and no equivalent on other providers (recorded per provider in the mapping table).
- Private repos run CI only on their self-hosted runners; a PR whose checks did not run there is `fix` (run the overlay's runner check), never merged.
- Processes are stopped by PID only. No AI attribution in any commit, PR, comment or file.

## 9. Duties per repo

1. **PRs**: section 6.
2. **Vulnerabilities**: provider alerts plus neutral scanners on a clone; fixes that are a patch or minor bump go through the same rules as a bot PR (everkeep opens its own PR on a branch `everkeep/fix-<id>`); the provider's alerting, security updates and private vulnerability reporting are switched on where off (decision D11 lists which settings everkeep may change without asking).
3. **Dependencies and toolchains**: straightforward bumps (patch or minor, past cooldown, green CI, clean lockfile) become everkeep PRs that merge under the rules; majors and anything breaking escalate as an issue or a draft PR with the evidence. Toolchain floors: Node 22/24/26 (20 is end of life; 24 enters maintenance 2026-10-20, 26 becomes LTS 2026-10-28), .NET 10 (8 and 9 end 2026-11-10), Unity 6.3 LTS (6.0 LTS ends October 2026), no Actions on node20 or older. Dated deadlines the gaps duty checks each run and lists at the top of the digest until they pass: `pull_request_target` blocked by default on public repos without an event policy from 2026-11-02 (list every workflow using it and escalate); NuGet API keys created before 2026-08-17 expire 2026-11-01 (any repo still publishing with a stored key needs trusted publishing first); npm stops accepting bypass-2FA tokens in January 2027.
4. **Modernization gaps**: the gap table (SECURITY.md from the tiered templates, README banner, topics, icon, Dependabot config with cooldown and groups, actions pinned by SHA with read-only tokens, ruleset, CodeQL default setup on public repos, trusted publishing where the registry trusts the CI, wiki for public packages, size-budget gate, AGENTS.md with CLAUDE.md importing it on its first line, a short CONTRIBUTING.md and AI-contribution policy so closing comments have a written rule to cite (GitHub plans CONTRIBUTING-based triage), and the open-PR cap of 1 for users without write access). Cheap fixes are applied in one everkeep PR per repo; the banner goes through an image generator when one is available, otherwise it stays a gap; a package missing a golden recording, a gated release or a verify-published workflow gets a package-modernize kickoff prompt written to the overlay's prompts folder instead of a fix.
5. **Knowledge base**: no `ai-docs/` means `everlast.py project register <clone> --mode repo --sync push` (private or work repos: decision by the overlay), then each sweep appends one log entry: what changed, what was decided, what is pending. A new knowledge base starts with the build and test commands that work, verified once (Microsoft's dotnet/runtime data: written build instructions lifted agent success from 38 to 69 percent).
6. **Ecosystem research**: one dated note per repo in `ai-docs/notes/`, with sources: dependents and downloads trend, competing and adjacent packages, where similar repos are going, upcoming platform deprecations. Clusters get an everscout beat each (.NET libraries, npm utilities, Unity packages, agent-skill plugins), created once and scanned on everscout's schedule; everkeep reads the beat's signals into the note. Reddit through RSS at one request per 30 to 60 seconds. Sources the CLI calls (all keyless, response shapes recorded in the research note): ecosyste.ms with `?mailto=` in the query (15,000 an hour; the user-agent alone stays at 5,000), deps.dev v3 and v3alpha (dependents, similarly named packages as a typosquat check), npm downloads, pypistats, NuGet search (`totalDownloads`, `owners`), OpenUPM `api.openupm.com/packages/extra` (`dl30d` for every package in one call), HN Algolia, release Atom feeds. Not OSS Insight trends (empty since 2026-03-01) and not libraries.io (10 requests without a key).
7. **Report**: section 10.

## 10. The digest

One per run, Markdown, saved to `~/.everkeep/runs/<run-id>/digest.md` and printed. Grouped by provider, then: **Merged**, **Closed**, **Bumped**, **Fixed** (bot PRs repaired, alerts cleared, gaps filled), **Waiting for Mark** (each with its URL and one-line reason; on GitHub these are already on his list at https://github.com/pulls?q=is%3Aopen+is%3Apr+assignee%3Am4bwav+archived%3Afalse), **Held** (cooldown, pending checks, widening stopped), **Not checked** (capability or tool missing, with the fallback used), **Knowledge base** (set up, notes written). A dry run's digest has the same sections in the conditional ("would merge").

Alert channel (decision D3): the GitHub list is the channel. Optional extras: a Todoist task linking the digest, or a push notification, never one message per repo.

## 11. Tests, evals, CI and size

- `tests/` with stdlib `unittest`: URL parsing for every provider's remote forms; scope resolution and filters; the classification table row by row with fixtures from the live snapshot (the NuGet lockfile that drops `net48` must classify `escalate` or `fix`, never `merge`); the lockfile-diff checker on npm and NuGet fixtures; the run file's resume; the seam test through the fake adapter with `gh` off PATH; `act` refusing a merge when the head SHA moved.
- `.github/workflows/tests.yml`: Ubuntu, Windows, macOS on Python 3.10 and 3.14, actions pinned by SHA, `permissions: contents: read`, zizmor clean.
- Evals (evergreen-test): triggers at each scope ("maintain this repo" stays on the current repo; "maintain my NuGet packages" resolves a selection; "maintain all my repos" goes account-wide; "check my repos" defaults to the current repo and offers to widen); a GitLab or Codeberg clone reports "not supported yet" and does nothing else; decoys "modernize my NuGet library" (package-modernize) and "what's new in agent skills this week" (everscout); action cases proven outside the transcript (a run file on disk, a label on a PR in a test repo, a digest file).
- **Size budget** (Mark's rule: small enough to install without hesitation), measured by `scripts/size_check.py` in CI:

| Measure | Green | Yellow (warn, ask Mark) | Red (CI fails) |
|---|---|---|---|
| Installed plugin, excluding `.github/images/` | under 400 KB | 400 KB to 1 MB | over 1 MB |
| `SKILL.md` body | under 4,000 tokens | 4,000 to 5,000 | over 5,000 |
| Skill description (listing cost) | under 700 characters | 700 to 1,024 | over 1,024 (spec limit) |
| `keep.py` package, lines | under 4,000 | 4,000 to 6,000 | over 6,000 |
| Third-party runtime dependencies | 0 | | any |

## 12. Decisions table (for Mark)

Already decided, not asked again: one repo per run by default; GitHub only in this build with other providers designed for; a public repo `m4bwav/everkeep` with the full treatment (banner, icon, SECURITY.md with private reporting, topics, README, wiki, CI, evals) (Mark, 2026-10-13).

| # | Decision | Recommendation | Why | Alternative |
|---|---|---|---|---|
| D1 | Name | **everkeep** | Free on GitHub (no m4bwav repo, only unrelated 0-star repos), npm and NuGet, and in no installed plugin. PyPI `everkeep` is reserved by an unrelated storage product (everkeep.dev); everkeep never publishes to PyPI. `keepwright` is already a Claude Code skill repo doing similar work, a worse collision. | `repowright` |
| D2 | Scheduling | **None until the live rollout ends**; then a weekly Windows task running headless `claude -p` on the selection `routine` (bot PRs and alerts only), with a narrow tool allow-list and no web access | A headless run reads hostile PR text; start with Mark watching. Routine bot work is where a schedule saves time | No schedule ever; or `/schedule` in the cloud (but private repos and the PC's runners are local) |
| D3 | Alert channel | **GitHub review list only**, plus the digest file | One place Mark already checks; no new noise | Also a Todoist task per run, or a push notification |
| D4 | `--all` for Mark | **Private repos included, forks and archived excluded** | About a third of the account is private and active; forks are other people's code | Plugin default (private excluded) |
| D5 | Starter selections | **`plugins`** (agent-skill plugin repos), **`npm`** (7), **`nuget`** (6 repos), **`low-risk`** (tier low or medium, not shared), **`routine`** (all non-fork repos, duties prs and vulns only) | Match the rollout order and the schedule | Fewer; or by topic |
| D6 | Risk tiers | **high** = RandomNameGeneratorLibrary, JsonPrettyPrinter, and any package over 100,000 total or 2,000 in six weeks; **medium** = other published packages; **low** = the rest | Matches the CLAUDE.md rule's examples; the seven npm packages' 500 to 1,000 a month are mostly mirrors | Lower thresholds (TrailerClipper's 17k total would become high) |
| D7 | Dependabot's own action pin bumps (they touch workflows) | **Merge** when the diff only changes `uses:` SHA and version comment lines of a first-party action (`actions/*`, `github/*`), patch or minor, past cooldown, green; escalate everything else in workflows | Six such PRs were open today; escalating each week buries real escalations. The CLI proves the diff is pin-only | Escalate all workflow changes; or exclude `release.yml` from the exception |
| D8 | Skill split | **One listed skill** with duty references | Catalog already 12.3K tokens over a 2K budget; one boundary to defend | Five skills (hub, prs, deps, gaps, research) |
| D9 | Closing human PRs | **Close on their own** only above the spam threshold with the model's read; below it, escalate with "recommend close" | No human PRs are open today; a wrong close costs a contributor | Always escalate first for the first month |
| D10 | Overlay location | **Vault sidecar** `vault/projects/everkeep/private/`, junctioned to `~/.everkeep/overlay` | Private, backed up, beside the other overlays | A folder in another private repository |
| D11 | Settings everkeep may change without asking | **Switching on** Dependabot alerts and security updates, secret scanning and push protection, private vulnerability reporting, CodeQL default setup (public repos), the open-PR cap for users without write access; **asking first** for rulesets, immutable releases, Actions policy, and anything that switches a protection off | The overlay already allows applying settings and secret scanning through `gh`; rulesets and release settings change how Mark works | Ask for every setting |
| D12 | Fixing a failing Dependabot PR | **Push the fix to Dependabot's branch** | Keeps one PR with its history; Dependabot stops rebasing a branch someone else pushed to, which is fine once it is green and merged the same day | Close it and open an everkeep PR |
| D13 | Learning mode for the shakedown | **On for the first account-wide runs**: verdict comments on every PR, no other action, until Mark has seen a run he agrees with; then per selection, `low-risk` first | Mark wants to run it on all repos to meet real-life mess; comments make every call visible and reversible | Act from the first run under the rules (rollout order only) |
| D14 | A lockfile adding a transitive package | **Escalate only with a danger signal** (decided 2026-10-14, built 2026-10-14): the new package shares no owner with the packages the same update moves (the bumped packages and the lockfile entries whose version changed; the direct package alone was too narrow, since NUnit3TestAdapter is NUnit's and the helper it pulls in is Microsoft's, like the Microsoft.Testing packages the same bump moves), is brand new, is not on its registry, has a near-miss name, comes from an odd source or adds an install script, or is a known-compromised version; otherwise it is a reason in the comment, not an escalation | A patch bump of a test adapter pulling in its own publisher's helper package (IsImageUrlDotNet#17) is routine; Mark: "only if it seems dangerous" | Every new transitive package escalates (the 0.1.0 rule) |

### Mark's answers (2026-10-13)

Asked in one batch: D4 "Private in, forks out", D6 "RNG + JsonPrettyPrinter" (plus the 100k-total or 2k-in-six-weeks threshold), D7 "Merge pin-only first-party", D2 "Weekly, after rollout". Not asked, so the recommendation stands: D1 everkeep, D3 GitHub list only, D5 starter selections, D8 one listed skill, D9 close only above the threshold, D10 vault sidecar, D11 switch-ons without asking, D12 push the fix to Dependabot's branch, D13 learning mode first (Mark's own idea). Status of this plan: approved, Phase 2 next.

## 13. Rollout

Phase 2 builds it (everlast-setup on this repo, CLI and tests, the skill via evergreen-new, registration in evergreen, the mark-local marketplace, install as `everkeep@mark-local`). Phase 3 dry runs: this repo, then a selection (one npm, one NuGet, one plugin: e.g. replace-string-at-position, CachingServiceWithAOPSupport, readwright), then `--all`, interrupted once and resumed, with 10 classifications checked by hand; stop and show Mark the all-repo digest. Between them comes the shakedown Mark asked for: learning mode (D13) on all repos, verdict comments only, corrections folded into LEARNINGS.md and the rules. Phase 4 then applies in the same widening order. Phase 5 tests and publishes.

Effort (agent time): Phase 2 is the bulk, about 3,000 to 4,000 lines of Python and tests plus about 15 Markdown files, roughly two long sessions; Phase 3 one session; Phases 4 and 5 one to two sessions, most of it waiting on CI and fixing what the dry run finds.
