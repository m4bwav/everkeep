# Research: everkeep

Findings that back [SKILL.md](SKILL.md). Changes they caused are logged in [CHANGELOG.md](CHANGELOG.md); procedural lessons live in [LEARNINGS.md](LEARNINGS.md); test runs and their evidence in [TESTS.md](TESTS.md); schedule and state in `evergreen.json`. Protocol: MAINTENANCE.md. The full Phase 0 notes, with every URL and read date, are in the repository's [ai-docs/research/](../../ai-docs/research/) folder; this file holds what the skill depends on.

Topic: Maintaining GitHub repositories and packages with an AI agent: PR triage of Dependabot/Renovate and human PRs, cooldowns and supply-chain signals (lockfile diffs, publisher changes, compromised versions), GitHub REST/gh behaviour (async merge, alerts, rulesets, PR caps, rate limits), vulnerability scanners (osv-scanner, npm audit, dotnet), toolchain EOL dates, AI-PR spam signals, other hosts (GitLab, Forgejo/Gitea, Bitbucket, Azure DevOps). Tier `fast`. Last refresh 2026-10-13; next due 2026-10-27.

## Current understanding

- **Split judge from actor.** Every serious 2026 incident (Clinejection, GitLost, TrustIssues) came from an agent that read hostile text while holding write tools. gh-aw's architecture (read-only agent, typed "safe outputs" applied by a separate job, per-run caps) is the reference design; everkeep does the same locally: the model returns a plan, `keep.py act` applies an allowlist with guards re-checked at action time. High confidence.
- **Cooldown from the registry's own publish time.** Bot and package-manager age gates have failed (Renovate skipped its gate on digest updates, CVE-2026-88884, fixed 44.3.1; pnpm 10.14 ignored `minimum-release-age` in the Nx Console incident). npm `time`, NuGet registration `published`, PyPI `upload_time`, the .NET release metadata and GitHub release dates are the sources; all answered keylessly on 2026-10-13 (`registries.py`). High confidence.
- **Provenance is not safety.** TanStack, Miasma and IronWorm all published through the victim's own OIDC pipeline with valid attestations; a publisher change or a downgrade from trusted publishing is a signal, valid provenance clears nothing. High confidence.
- **Dependabot's NuGet updater drops target sections.** On 2026-10-13 three PRs rewrote `packages.lock.json` without the `net48` and `win-x86` sections, failing locked restores; a lockfile check must flag removed targets, not only added packages (live snapshot, tests/fixtures). High confidence; watch for a Dependabot fix.
- **GitHub API facts the adapter relies on:** async merge `PUT /pulls/{n}/merge-async` with `sha` (GA 2026-10-01; 202 then poll `details.uuid`; 409 another pending); withdrawn Dependabot alerts answer 410 (2026-10-13); archiving a PR is UI-only (2026-10-08); open-PR cap for users without write access is a repo setting; no account-wide alert listing for personal accounts; 5,000 REST requests an hour, content creation 80 a minute and 500 an hour, writes one at a time a second apart. High confidence (docs read 2026-10-13).
- **Dated platform deadlines:** NuGet API keys made before 2026-08-17 expire 2026-11-01; `pull_request_target` blocked by default on public repos without an event policy from 2026-11-02; .NET 8 and 9 end 2026-11-10; Unity 6.0 LTS ends October 2026; node20 actions stopped 2026-09-23; npm 2FA-bypass tokens end January 2027. High confidence; recheck each refresh.
- **Slop handling:** maintainers chose platform controls (PR caps, collaborators-only, Vouch lists, CONTRIBUTING-based rules) over detection; anti-slop's scoring has documented false positives (digits in usernames, URL counts, maintainer "Update branch" commits). Close only on several signals including a content signal, from the owner's login so it can be reopened, citing a written rule. Medium-high confidence.
- **Headless runs are dangerous inside a repo:** `claude -p` shows no trust dialog and runs the repo's hooks and `.mcp.json` servers; a scheduled run must start outside any repo with hooks off, no MCP, a narrow tool allow-list. Medium confidence on the exact flags (they change between releases).
- **Tooling:** no published "maintain all my repos" agent by a solo developer was found; closest are gh-aw's `repo-assist` (one repo per workflow) and multi-gitter, turbolift and all-repos (frozen list, dry run, one branch per campaign, resumable), whose shape the run engine copies. `keepwright` (a Claude Code skill for repo quality) exists and overlaps in name only.

## Open questions

- Whether GitHub's Dependabot NuGet updater fixes the dropped-target-section bug (issue to find and watch).
- CodeRabbit slop detection on the free public tier (docs say yes, pricing page says paid).
- The exact `claude -p` flag set for a locked-down run (`--tools`, `--setting-sources`, `disableAllHooks`): test before any schedule.
- Other hosts' open items (GitLab secret push protection on Free, Bitbucket fork pipelines, Azure fork builds, `fj`/`tea` JSON output): in the repository's providers roadmap.

## Search plan

Four tracks; every refresh runs at least one query on each (scope each to the period since the last refresh; add the year).

Subject:

- `site:github.blog/changelog dependabot OR "pull request" OR "code scanning" OR rulesets <month> <year>`
- `npm OR NuGet OR PyPI "trusted publishing" OR "malicious package" OR "supply chain" <month> <year>`
- `dependabot nuget "packages.lock.json" target framework removed` (the dropped-section bug)
- `site:docs.github.com rest pulls merge-async` and `rest "interaction-limits" creation-cap`
- `endoflife.date/api/v1/products/nodejs/`, `/dotnet/`, `/unity/` (dates in references/deps.md and gaps.md)
- `pull_request_target "event policy" 2026-11-02`

Tooling:

- `path:SKILL.md "dependabot" OR "pull request triage" OR "maintain repositories"` on GitHub code search, sorted by recently updated; `npx skills find "repo maintenance"` and skills.sh
- `https://registry.modelcontextprotocol.io/v0/servers?search=github` (new GitHub MCP servers or triage servers)
- `gh api repos/github/gh-aw/releases` (gh-aw moves weekly); `"repo-assist" OR "agentic workflows" triage <year>`
- `"multi-repo" OR "all my repos" agent maintain claude OR codex <year> site:github.com`; archive flag on keepwright, anti-slop, vouch
- Supersession sweep: `"dependabot" auto-merge agent skill deprecated OR superseded <year>`

Practice:

- `"AI maintainer" OR "vibe maintainer" OR "agent merges" open source <year>`
- `hn.algolia.com/api/v1/search_by_date?query=dependabot%20agent` and `?query=AI%20pull%20requests%20maintainer`
- `site:devblogs.microsoft.com "copilot" "dotnet/runtime" pull requests` (review-time data)
- Reddit RSS (one request per 30 to 60 seconds): r/opensource, r/dotnet, r/node "AI PRs" or "Dependabot"

Testing:

- `"pull request" triage agent evaluation OR benchmark <year> site:arxiv.org`
- `path:SKILL.md "dependabot" evals OR tests` on GitHub
- How others prove a merge bot is safe: gh-aw staged mode and threat-detection docs; anti-slop's issue tracker for false positives

Best sources (primary first): the GitHub changelog and REST docs, npm/NuGet/PyPI blogs and docs, endoflife.date, gh-aw docs and releases, the anti-slop and Vouch repositories, Microsoft devblogs. Sources that proved noisy: OSS Insight trends (empty since 2026-03-01), libraries.io without a key, SEO listicles of "best GitHub bots".

## Findings log

- R-20261030-1 (quiet check, all tracks): nothing newer since last_checked for everkeep; subject, tooling, practice, testing: nothing new. Sources: web searches (Claude Code changelog, arXiv agent memory, Dependabot changelog, npm compromises). m 0. applied: none.

Newest first. One entry per material finding; a quiet refresh gets one entry saying so. `Track` is subject, tooling, practice, or testing.

### R-20261013-4 · 2026-10-13 · Testing: evidence lives outside the transcript
- Summary: gh-aw's staged mode and the sweep tools' dry runs show the accepted proof shape: a run file and a digest on disk, and on a host, a label or comment that can be read back. everkeep's action cases use the run file, the digest and the fake adapter's recorded writes; live cases use a verdict comment's hidden marker.
- Track: testing
- Sources: https://github.github.com/gh-aw/reference/safe-outputs/ (read 2026-10-13); multi-gitter and all-repos READMEs (repo research note section 7)
- Magnitude: n/a (initial)
- Applied: C-20261013-1

### R-20261013-3 · 2026-10-13 · Practice: platform controls first, agents read and propose
- Summary: Ghostty (Vouch), llama.cpp (one open PR for newcomers, now a GitHub setting), tldraw and curl chose blunt controls; Yegge's "Vibe Maintainer" (2026-03-31) keeps every taste decision with a human; Microsoft's dotnet/runtime data says preparation and review time dominate. Became the caps, learning mode, templated closes and the CONTRIBUTING gap.
- Track: practice
- Sources: https://github.com/mitchellh/vouch, https://hn.algolia.com/api/v1/items/46930961, ai-docs/research/2026-10-13-maintainer-bots-and-practice.md (all read 2026-10-13)
- Magnitude: n/a (initial)
- Applied: C-20261013-1

### R-20261013-2 · 2026-10-13 · Tooling: nothing to build on for "maintain all my repos"
- Summary: no maintained skill, plugin or MCP server does account-wide maintenance for a solo maintainer. gh-aw (one repo per workflow, Actions minutes, AI credits), Mergify (merge queues, not needed at this volume), CodeRabbit (label-only slop note) and anti-slop (Action, AGPL, false positives) cover slices; everkeep configures the platform where it can and borrows the sweep tools' run shape.
- Track: tooling
- Sources: https://github.github.com/gh-aw/introduction/architecture/, https://mergify.com/pricing, https://docs.coderabbit.ai/pr-reviews/slop-detection, https://github.com/peakoss/anti-slop (all read 2026-10-13)
- Magnitude: n/a (initial)
- Applied: C-20261013-1

### R-20261013-1 · 2026-10-13 · Subject: Phase 0 research (four agents) and the live snapshot
- Summary: verified the landscape note's open items, the month's GitHub, npm, NuGet, PyPI and Node changes, trusted-publishing support per registry, API limits and endpoints, other providers' APIs, scanners and EOL APIs; the live snapshot found 19 open Dependabot PRs, 4 failing, 3 from the NuGet dropped-target bug. Registry publish-time endpoints and the async-merge contract re-checked while building (docs.github.com REST pulls, 2026-10-13).
- Track: subject
- Sources: ai-docs/research/2026-10-13-verification-and-recent-changes.md, -ecosystem-apis-scanners-eol.md, -other-providers.md, -live-account-snapshot.md; https://docs.github.com/en/rest/pulls/pulls (read 2026-10-13)
- Magnitude: n/a (initial)
- Applied: C-20261013-1
