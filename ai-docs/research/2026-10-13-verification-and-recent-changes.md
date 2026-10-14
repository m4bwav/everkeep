# Everkeep Phase 0: verification and recent changes (2026-10-13)

Follow-up to the 2026-10-13-landscape note (kept outside this repository). It checks that note's "Not verified" list, walks the GitHub, npm, NuGet, PyPI, .NET and Node changes from 2026-09-10 to 2026-10-13, records which CI providers each registry's trusted publishing accepts, and lists the GitHub API limits and REST endpoints an account-wide sweep needs. Every URL below was read on 2026-10-13. Three helper research agents fetched some pages for this note; every one of those pages is cited, and the key ones were re-read directly.

## Summary

Most open items now check out, but some details differ from what the landscape note assumed. Dependabot's merge, close and reopen comment commands were removed on 2026-01-27. Renovate CVE-2026-88884 is real: digest updates skipped `minimumReleaseAge`, fixed in 44.3.1. All four npm items are real and dated: multiple trusted-publishing configs (09-03), stage-only tokens (09-18), dist-tag permission (09-30), and unvalidated configs expiring after 48 hours (10-02). That last item also blocks OIDC publishing from `issue_comment` runs. NuGet trusted publishing launched on 2025-09-22, and NuGet API keys made before 2026-08-17 expire on **2026-11-01**. Miasma was mostly not forged provenance: a hijacked repository used its own legitimate OIDC workflow, so the attestations were genuine. Only Microsoft claims a forged-provenance stage, with no detail. The PR cap has its own REST endpoint under `interaction-limits`. Personal accounts have no account-level SHA-pinning switch, so the sweep sets it repo by repo. No registry accepts self-hosted runners for trusted publishing (npm says so outright; NuGet's docs neither allow nor rule them out). That matters for Mark's private repos, which build on self-hosted runners. Key upcoming dates:

| Date | What happens |
|---|---|
| 2026-10-20 | Node 24 enters maintenance |
| 2026-10-28 | Node 26 becomes LTS |
| 2026-11-01 | Old NuGet API keys expire |
| 2026-11-02 | `pull_request_target` is blocked by default on affected public repos; macOS 14 runner image retired |
| 2026-11-10 | .NET 8 and 9 reach end of support |
| 2026-11-30 | Stateless app-token header deprecated |
| January 2027 | npm removes publishing with bypass-2FA tokens |

## 1. The landscape note's "Not verified" list

**Dependabot comment-command removal: verified.**
- Retired on 2026-01-27. The retired commands are `@dependabot merge`, `cancel merge`, `squash and merge`, `close` and `reopen`. GitHub says to use "GitHub's built-in UI, the GitHub CLI, and the REST API endpoints for pull requests." https://github.blog/changelog/2026-01-27-changes-to-github-dependabot-pull-request-comment-commands/ (read 2026-10-13)
- Announced 2025-10-06/07. https://github.blog/changelog/2025-10-06-upcoming-changes-to-github-dependabot-pull-request-comment-commands/ (read 2026-10-13)
- Commands still supported:
  - `@dependabot rebase` and `recreate`.
  - The `ignore this dependency/major/minor/patch version` and `show ... ignore conditions` commands.
  - On grouped and security PRs, `ignore DEPENDENCY_NAME`, `unignore *` and `unignore DEPENDENCY_NAME`.

  https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-pull-request-comment-commands (read 2026-10-13)

**Renovate CVE-2026-88884: verified, and it exists.**
- Title: "Renovate before 44.3.1 Authentication Bypass via Digest Updates", CWE-863.
- Mechanism: digest updates were not subject to `minimumReleaseAge`. Renovate could open a PR for a brand-new digest (SHA-pinned Actions, Docker, Go, NuGet) with only a pending `renovate/stability-days` check, so CI ran on it early.
- Fixed in Renovate 44.3.1, Mend CE/EE images 15.4.0, the CE Helm chart 15.4.0 and the EE Helm chart 10.4.0.
- Workaround: disable digest updates or gate them behind `dependencyDashboardApproval`.
- VulnCheck (the CNA) published the CVE on 2026-09-10; the alias is GHSA-g4qr-hw2h-687r. https://api.osv.dev/v1/vulns/CVE-2026-88884 (read 2026-10-13)
- The repo advisory was published 2026-08-27 and rated Moderate. https://github.com/renovatebot/renovate/security/advisories/GHSA-g4qr-hw2h-687r (read 2026-10-13)
- Design point: a cooldown that only one bot honours is not a gate; CI must not trust a bot PR's age claim.

**npm September/October 2026 items: all verified.**
- **Multiple trusted-publishing configurations (2026-09-03).**
  - Each configuration is independent, and a publish is authorized if any one matches.
  - "Every trusted publishing configuration can stage a package by default"; direct publish is opt-in per configuration.
  - Approval of a staged version waits for malware scanning to finish.
  - https://github.blog/changelog/2026-09-03-multiple-trusted-publishing-configurations-for-npm (read 2026-10-13)
  - The npm docs cap it at 10 configurations per package. https://docs.npmjs.com/trusted-publishers (read 2026-10-13)
- **Stage-only tokens (2026-09-18).**
  - New granular permission "Read and write (stage only)": `npm publish` is rejected even with bypass-2FA, and a maintainer approves each version with 2FA.
  - The token can still move dist-tags and deprecate versions.
  - Needs npm 11.15.0+ and Node 22.14.0+.
  - npm targets **January 2027** for removing direct publishing with bypass-2FA tokens.
  - https://github.blog/changelog/2026-09-18-stage-only-npm-tokens-for-safer-automation (read 2026-10-13)
- **Opt-in dist-tag permission (2026-09-30).**
  - A per-configuration "Allow npm dist-tag" setting, off by default for new and existing configurations.
  - https://github.blog/changelog/2026-09-30-opt-in-dist-tag-permissions-for-npm-trusted-publishing (read 2026-10-13)
  - Needs npm CLI 11.21.0+ or 12.2.0+. https://docs.npmjs.com/trusted-publishers (read 2026-10-13)
- **Unvalidated configurations expire (2026-10-02).**
  - A configuration expires 48 hours after creation unless it has published once; changing the repo or project identity starts a new window.
  - npm now also rejects trusted-publishing tokens from `issue_comment` events, on top of `pull_request_target`.
  - https://github.blog/changelog/2026-10-02-unvalidated-npm-trusted-publishing-configurations-now-expire (read 2026-10-13)
- **Staged publishing can create new packages (2026-10-02).**
  - `npm stage publish` can create a package, but a maintainer must promote the first version.
  - https://github.blog/changelog/2026-10-02-npm-staged-publishing-now-supports-creating-new-packages (read 2026-10-13)

**NuGet trusted publishing month: verified.**
- Launched on 2025-09-22 ("Enhanced security is here with the new Trust Publishing on NuGet.org"). The post does not use the words GA or preview. https://devblogs.microsoft.com/dotnet/enhanced-security-is-here-with-the-new-trust-publishing-on-nuget-org/ (read 2026-10-13)
- Temporary keys last 1 hour, with one key per OIDC token.
- Policies for private GitHub repos start "temporarily active for 7 days" until a first publish.
- GitLab CI/CD is now documented too. https://learn.microsoft.com/en-us/nuget/nuget-org/trusted-publishing (read 2026-10-13)
- API key lifetimes (2026-08-03 post):
  - New keys are capped at 30 days from 2026-08-17.
  - **All keys created before 2026-08-17 expire on 2026-11-01.**

  https://devblogs.microsoft.com/dotnet/strengthening-nuget-supply-chain-security-reducing-api-key-lifetime/ (read 2026-10-13)

**2026 attacks.**
- **Axios: verified.**
  - On 2026-03-31, `axios@1.14.1` and `0.30.4` were live from 00:21 to 03:15 UTC. Both added `plain-crypto-js@4.2.1`, whose postinstall dropped a cross-platform RAT.
  - Vector: social engineering of the lead maintainer, whose npm account was taken over despite 2FA. Publishing used a long-lived token, not OIDC.
  - Maintainer post-mortem: https://github.com/axios/axios/issues/10636 (read 2026-10-13)
  - Microsoft attributes it to Sapphire Sleet (from search summaries; the vendor post was not opened).
- **nx: partly verified.** The 2026 incident hit the Nx Console VS Code extension 18.95.0 on 2026-05-18 (12:30 to 13:09 UTC), CVE-2026-48027. The `nx` npm package was not affected.
  - Root cause: a contributor's `pnpm install` pulled a malicious TanStack package, which stole their `gh` OAuth token.
  - The repo's 7-day `minimum-release-age` did nothing, because pnpm 10.14 silently ignores it (support arrived in 10.16).
  - Fixes: a second-reviewer gate on publishing and SHA-pinned actions.
  - https://nx.dev/blog/nx-console-v18-95-0-postmortem (read 2026-10-13)
- **Megalodon: verified, from a security-vendor source.**
  - On 2026-05-18, forged commits backdoored about 5,561 public repos in six hours. The commits pushed workflows (`SysDiag`, `Optimize-Build`) straight to weakly protected default branches; the workflows stole secrets and minted OIDC tokens.
  - Spillover: `@tiledesk/tiledesk-server` 2.18.6 to 2.18.12.
  - How the attackers got write access is not established.
  - https://stepsecurity.io/blog/megalodon-mass-github-actions-secret-exfiltration-across-5-500-public-repositories (read 2026-10-13)
- **IronWorm: verified.**
  - JFrog, 2026-06-03: a Rust stealer and worm in 36 or 37 npm packages, with an eBPF rootkit and Tor command and control.
  - It pushes backdated commits authored as `claude@users.noreply.github.com`, and inside CI it swaps OIDC for npm publish tokens (trusted publishing abused, not bypassed).
  - https://research.jfrog.com/post/iron-worm-shai-hulud-rustier-cousin/ and https://www.bleepingcomputer.com/news/security/new-ironworm-malware-hits-36-packages-in-npm-supply-chain-attack/ (read 2026-10-13)
- **"Comment and Control": verified as published research, not an in-the-wild campaign.**
  - Aonan Guan and others, 2026-04-15: prompt injection through PR titles, issue bodies and comments made Anthropic's claude-code-security-review action, Google's run-gemini-cli action and Copilot's coding agent leak secrets.
  - No CVEs were issued.
  - https://oddguan.com/blog/comment-and-control-prompt-injection-credential-theft-claude-code-gemini-cli-github-copilot/ and https://labs.cloudsecurityalliance.org/research/csa-research-note-comment-control-github-prompt-injection-20/ (read 2026-10-13)

**Miasma forged provenance: refuted as stated, with one open claim.**
- Red Hat's bulletin RHSB-2026-006: a compromise on 2026-05-29 of a GitHub account (via a malicious VS Code extension), 32 `@redhat-cloud-services` packages affected, no customer action needed. It says nothing about provenance. https://access.redhat.com/security/vulnerabilities/RHSB-2026-006 (read 2026-10-13)
- Wiz: orphan commits added a release workflow with `id-token: write` that published "with valid SLSA provenance attestations", meaning the legitimate pipeline identity was hijacked. https://www.wiz.io/blog/miasma-supply-chain-attack-targeting-redhat-npm-packages (read 2026-10-13)
- Microsoft alone says a later worm stage "republished poisoned packages with forged SLSA provenance", with no technical detail. https://www.microsoft.com/en-us/security/blog/2026/06/02/preinstall-persistence-inside-red-hat-npm-miasma-credential-stealing-campaign/ (read 2026-10-13)
- Treat the forged-provenance claim as unverified. The safe rule stands either way: valid provenance does not prove safe code.

**claude-code-action CVEs: verified.**
- **CVE-2026-47751 / GHSA-8q5r-mmjf-575q.**
  - Versions before 1.0.74 read `.mcp.json` from an attacker's PR head branch and enabled its MCP servers, giving code execution on the runner and secret exfiltration.
  - The fix restores `.claude/` and `.mcp.json` from the base branch. CWE-78 and CWE-200.
  - https://api.osv.dev/v1/vulns/CVE-2026-47751 (read 2026-10-13)
  - The repo's advisory index lists only this one advisory (Moderate, published 2026-05-20). https://github.com/anthropics/claude-code-action/security/advisories (read 2026-10-13)
  - Dates conflict: the repo says 2026-05-20, OSV 2026-07-16. Tenable TRA-2026-27 gives the fix as 1.0.78. https://ar.tenable.com/security/research/tra-2026-27 (read 2026-10-13)
- **Uncatalogued "bot-suffix" bypass (GMO Flatt Security), fixed in 1.0.94, no CVE.**
  - Any actor whose name ended in `[bot]` passed the write-permission check.
  - A prompt-injected issue made Claude dump `/proc/self/environ`, and the leaked OIDC request values could be swapped for a Claude GitHub App write token.
  - https://flatt.tech/research/posts/poisoning-claude-code-one-github-issue-to-break-the-supply-chain/ (read 2026-10-13)
- **Pin claude-code-action at 1.0.94 or later**, not 1.0.74 as the landscape note says.

**OSS Insight API: verified.**
- "OSSInsight Public APIs (beta)" at `https://api.ossinsight.io/v1`, no authentication.
- Limits: 600 requests per hour per IP and 1,000 per minute globally, reported in `x-ratelimit-*` headers.
- https://ossinsight.io/docs/api (read 2026-10-13)

**libraries.io: verified, still running.**
- The API needs a free `api_key` and allows 60 requests per minute (429 above that).
- No shutdown notice. The repo is not archived; its last push was 2026-10-02.
- https://libraries.io/api and https://api.github.com/repos/librariesio/libraries.io (read 2026-10-13)
- I found no source for a move into ecosyste.ms.

**Socket PR comments on the free plan: partly verified.**
- The Free plan is $0: unlimited repos, 1,000 scans a month, 500 API calls an hour. Public OSI-licensed projects can request a free Business upgrade. https://socket.dev/pricing and https://docs.socket.dev/docs/faq (read 2026-10-13)
- The GitHub app posts alert comments and a Dependency Overview comment, both on by default. https://docs.socket.dev/docs/socket-for-github (read 2026-10-13)
- No page states either way whether Free includes PR comments.

**Sweep: verified as pivoted and apparently dormant.**
- The repo description reads "Sweep: AI coding assistant for JetBrains"; the last push was 2025-09-18. https://github.com/sweepai/sweep (read 2026-10-13)
- The JetBrains plugin's last release was 2026-02-05.
- sweep.dev and docs.sweep.dev fail DNS lookup.
- Do not plan around Sweep.

**Mergify: verified.**
- Products: Merge Queue, Merge Protections (dynamic rules on top of rulesets, merge freezes), Workflow Automation (a rule engine), CI Insights, Test Engine and Stacks. https://docs.mergify.com/ (read 2026-10-13)
- Plans: the Open Source plan is $0 with unlimited users (5 on private repos) and 24-hour data retention. Free covers up to 5 users. Max is $21 per seat per month. https://mergify.com/pricing (read 2026-10-13)
- Which tiers include Workflow Automation is not confirmed.

**Unity dates: partly verified.**
- 6.3 LTS was released 2025-12-04 and is supported to December 2027. https://unity.com/blog/unity-6-3-lts-is-now-available (read 2026-10-13)
- 6.0 LTS support ends "October 2026", with no exact day on Unity's page.
- LTS policy: one LTS a year, supported for two years, plus one more year for Enterprise and Industry customers.
- https://unity.com/releases/unity-6/support (read 2026-10-13)
- Current non-LTS release: 6.6 (2026-09-01). Its post says 6.7 will be the next LTS, with no date. https://discussions.unity.com/t/unity-6-6-is-now-available/1735357 (read 2026-10-13)

**OpenSSF Scorecard weights: verified.**
- Aggregate score = average of check scores weighted by risk: Critical 10, High 7.5, Medium 5, Low 2.5.

| Risk | Checks |
|---|---|
| Critical | Dangerous-Workflow, Webhooks |
| High | Binary-Artifacts, Branch-Protection, Code-Review, Dependency-Update-Tool, Maintained, Signed-Releases, Token-Permissions, Vulnerabilities |
| Medium | Fuzzing, Packaging, Pinned-Dependencies, SAST, SBOM, Security-Policy |
| Low | CI-Tests, CII-Best-Practices, Contributors, License |

- Latest release v5.6.0.
- https://raw.githubusercontent.com/ossf/scorecard/main/README.md and https://raw.githubusercontent.com/ossf/scorecard/main/docs/checks.md (read 2026-10-13)

## 2. What changed, 2026-09-10 to 2026-10-13

Source lists: https://github.blog/changelog/2026/09/ and https://github.blog/changelog/ (read 2026-10-13). Each item below links its own post (read 2026-10-13).

### GitHub: Actions security

- **2026-09-10, `cache-mode`.**
  - Values `read`, `write`, `write-only` and `none`, set per workflow or job.
  - `pull_request_target` defaults to read and `push` to write. Declaring write on a low-trust event triggers a warning.
  - https://github.blog/changelog/2026-09-10-control-github-actions-cache-access-with-cache-mode
- **2026-09-17, workflow execution protections GA.**
  - Actor and event allowlists, checked before a run, can be scoped to specific workflow files. There is a REST API, and evaluate mode remains.
  - Public repos with no event policy get a default rule that disables `pull_request_target`. **GitHub will enforce it on 2026-11-02 for affected repos**; private repos are excluded.
  - https://github.blog/changelog/2026-09-17-workflow-execution-protections-in-github-actions-generally-available
- **2026-09-23, Node 20 removed from Actions.**
  - JavaScript actions run on Node 24, and the `ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION` opt-out is gone.
  - Self-hosted runners on macOS 13.4 or older, or on ARM32, are unsupported.
  - Any of Mark's own actions with `runs.using: node20` must move to `node24`.
  - https://github.blog/changelog/2026-09-23-node-20-is-no-longer-available-in-github-actions
- **2026-09-28, self-hosted runner minimum.**
  - Runners must be 2.329.0+ to register, enforced from 2026-09-29.
  - The post scopes this to Enterprise Cloud. Check Mark's self-hosted runners anyway.
  - https://github.blog/changelog/2026-09-28-self-hosted-runner-version-enforcement-date-has-moved
- **2026-09-03 (just before the window), Actions updates.**
  - A new `vulnerability-alerts: read` permission for `GITHUB_TOKEN`.
  - New `job.workflow_sha` and related context properties.
  - A runner deprecation REST API.
  - https://github.blog/changelog/2026-09-03-github-actions-early-september-2026-updates
- **2026-10-01, retention.** Checks, runs and statuses now follow the retention setting; public repos keep them for at most 90 days. https://github.blog/changelog/2026-10-01-actions-retention-now-covers-checks-runs-and-statuses
- **2026-10-01, macOS 14 runner image.** Retired on 2026-11-02, with brownouts in October. https://github.blog/changelog/2026-10-01-github-actions-macos-14-runner-image-retirement
- **2026-10-02, stateless app installation tokens.**
  - Tokens are now about 520 characters (`ghs_APPID_JWT`).
  - The `X-GitHub-Stateless-S2S-Token` header is deprecated on 2026-11-30.
  - https://github.blog/changelog/2026-10-02-stateless-github-app-installation-tokens-rolled-out
- **2026-10-13, GitHub App permissions.**
  - New fine-grained permissions `repository_creation:write` and `installation_repositories:write`.
  - `offline_access` refresh tokens for apps.
  - https://github.blog/changelog/2026-10-13-github-app-improvements-for-least-privilege-and-management
- **SHA pinning: no new changelog post in the window.** The policy dates from 2025-08-15. The REST field is `sha_pinning_required` (section 4).

### GitHub: Dependabot

- **2026-09-08 (just before the window).** Automatic Dependabot access to GitHub-hosted registries. https://github.blog/changelog/2026-09-08-automatic-dependabot-access-to-github-hosted-registries
- **2026-09-29, repository custom runner settings.**
  - Runner type, label and group for Dependabot.
  - **Private and internal repos only, UI only**, with no API mentioned. This is useful for Mark's private repos on self-hosted runners.
  - https://github.blog/changelog/2026-09-29-repository-custom-runner-settings-for-dependabot
- **2026-10-12, anonymous org-level registries.** https://github.blog/changelog/2026-10-12-anonymous-organization-level-registries-for-dependabot
- **2026-10-13, withdrawn alerts.**
  - The `dependabot_alert` webhook gains a `withdrawn` action.
  - REST get or update on a withdrawn alert now returns **410 Gone** instead of 404. The agent must treat 410 as "advisory withdrawn, close out", not as an error.
  - https://github.blog/changelog/2026-10-13-improved-detection-for-withdrawn-dependabot-alerts

### GitHub: code scanning

- **2026-09-10, AI Scan for PR APIs.** Public preview, Advanced Security only. https://github.blog/changelog/2026-09-10-ai-scan-for-pull-request-apis-in-public-preview
- **2026-09-16, AI Scan.** No longer requires CodeQL default setup. https://github.blog/changelog/2026-09-16-code-scanning-ai-scan-no-longer-requires-codeql-default-setup
- **2026-09-22, CodeQL bundle.** The all-platform CodeQL bundle is deprecated, with removal in mid-March 2027. https://github.blog/changelog/2026-09-22-deprecation-notice-all-platform-codeql-bundle
- **2026-09-25, agentic autofix.** Now uses Copilot Memory. https://github.blog/changelog/2026-09-25-agentic-autofix-now-uses-copilot-memory
- **2026-10-01, scheduled scans skip inactive repos.**
  - Weekly default-setup scans now start only after a push or PR analysis.
  - Effect for Mark: enabling default setup across dormant repos no longer causes six months of weekly scans.
  - https://github.blog/changelog/2026-10-01-scheduled-code-scanning-skips-inactive-repositories
- **CodeQL releases.** 2.27.1 (09-25) and 2.27.2 (10-09). Routine; 2.27.2 was not read.

### GitHub: secret scanning

- **2026-09-09, merge-blocking ruleset rule.**
  - New rule "Require secret scanning alerts are resolved" (`require_secret_scanning_alert_resolution`).
  - Public preview, needs Secret Protection or Advanced Security.
  - https://github.blog/changelog/2026-09-09-block-pull-requests-with-exposed-secrets-from-merging
- **2026-10-05, new detectors.** Lovable, Supabase and others. https://github.blog/changelog/2026-10-05-secret-scanning-adds-detectors-for-lovable-supabase-and-more
- **2026-10-07, AI secret detection.**
  - A purpose-built AI detection model. AI push protection is in private preview and uses AI Credits.
  - https://github.blog/changelog/2026-10-07-purpose-built-model-for-leaked-secret-detection
- **2026-10-13, Anthropic keys.**
  - Push protection now blocks Anthropic service and user API keys by default, "including free public repositories".
  - Salesforce added.
  - https://github.blog/changelog/2026-10-13-secret-scanning-blocks-anthropic-keys-by-default-adds-salesforce

### GitHub: pull request controls and merging

- **2026-09-21, refreshed PR list page.** GA. https://github.blog/changelog/2026-09-21-refreshed-repository-pull-requests-page-generally-available
- **2026-10-01, async merge API GA.**
  - `PUT .../pulls/{n}/merge-async`, then poll the returned UUID. 202 means the merge is queued in the background; 409 means another request is pending.
  - GitHub now recommends it over the synchronous merge endpoint, and it is the only merge API that supports stacked PRs.
  - https://github.blog/changelog/2026-10-01-github-async-merge-api-generally-available and https://docs.github.com/en/rest/pulls/pulls
- **2026-10-06, stacked PRs GA.**
  - A stack lands through the merge queue as one group. Auto-merge for stacks is still rolling out.
  - https://github.blog/changelog/2026-10-06-stacked-pull-requests-generally-available
- **2026-10-08, drafts and PR limits.** Drafts can now count toward the open-PR cap (`include_drafts`). https://github.blog/changelog/2026-10-08-draft-pull-requests-count-toward-pull-request-limits
- **2026-10-08, archiving PRs.**
  - Triage role and above can archive PRs.
  - Archiving closes the PR, makes it read-only, blocks all new comments including bot comments, and hides it from the public.
  - No API is mentioned, and the Pulls REST docs have no archive endpoint.
  - https://github.blog/changelog/2026-10-08-triage-role-users-or-higher-can-now-archive-pull-requests
- **Linked-issue requirement and CONTRIBUTING-based triage: no changelog post found** in the window or by search. Still planned or unannounced.

### GitHub: rulesets, releases, advisories

- **Rulesets.**
  - 2026-09-18: the code-coverage ruleset condition can be managed via REST (needs Code Quality). https://github.blog/changelog/2026-09-18-manage-the-code-coverage-ruleset-condition-with-the-rest-api
  - 2026-10-12: push attribution and a "committer must match pusher" rule, Enterprise only. https://github.blog/changelog/2026-10-12-push-attribution-public-preview
- **Immutable releases: no changelog post in the window.** REST endpoints are in section 4.
- **Private vulnerability reporting, structured forms (2026-10-01).**
  - Default required fields are summary, details, proof of concept (at least 150 characters) and impact.
  - A custom form goes in `.github/VULNERABILITY_REPORT.yml`, or in the account's `.github` repo to apply everywhere.
  - Reporters see a link to SECURITY.md and an AI-assistance disclosure box.
  - Public repos only.
  - https://github.blog/changelog/2026-10-01-structured-forms-for-private-vulnerability-reports
- **Private vulnerability reporting, rate limits (2026-10-01).**
  - Daily per-user limits on new reports; the post gives no numbers.
  - Admins can set a repo daily cap and an allow list of trusted reporters.
  - https://github.blog/changelog/2026-10-01-rate-limits-for-private-vulnerability-reports
- **Security advisory comments (2026-10-02).**
  - Confidential maintainer-only comments, plus an advisory comments REST API in public preview.
  - https://github.blog/changelog/2026-10-02-confidential-comments-on-repository-security-advisories and https://github.blog/changelog/2026-10-02-repository-security-advisory-comments-api-in-public-preview
- **SecurityAdvisory GraphQL fields (2026-10-02).** New `cveId`, `isWithdrawn` filter and others. https://github.blog/changelog/2026-10-02-new-fields-for-securityadvisory-graphql-api

### GitHub: Copilot agents and code review

- **2026-09-01, Copilot can approve PRs.**
  - Copilot code review can submit an approval that counts toward required approvals.
  - Off by default; can be scoped to file paths; dismissed when new commits are pushed.
  - Relevant if the agent ever leans on Copilot approvals; Mark should decide whether that counts.
  - https://github.blog/changelog/2026-09-01-copilot-code-review-can-now-approve-pull-requests
- **Review features.**
  - 2026-09-11: auto-resolution of Copilot's own comments. https://github.blog/changelog/2026-09-11-auto-resolution-and-analysis-updates-in-copilot-code-review
  - 2026-09-23: automatic reviews from personal settings. https://github.blog/changelog/2026-09-23-copilot-code-review-more-ways-to-request-and-configure-reviews
  - 2026-10-02: reviews can be requested through REST and GraphQL with an effort level. https://github.blog/changelog/2026-10-02-copilot-code-review-api-support-and-new-default-effort-level
- **No posts in the window on assigning agents** to issues, PRs or alerts. The weekly Copilot posts for 09-14 through 10-05 have nothing on the coding agent.

### gh CLI

https://github.com/cli/cli/releases (read 2026-10-13)

- **2.101.0 (2026-09-15).** APT and RPM packages are signed with a new key, so stale keyrings will fail to update. Device codes are copied to the clipboard by default.
- **2.102.0 (2026-09-30).** Four security fixes:
  - Symlinked destinations in `release download`, `run download`, `repo read-file` and `attestation download`.
  - `attestation verify` matched `--source-ref` case-insensitively and `--signer-workflow` by prefix.
  - `skill search` option injection.

  **Require gh 2.102.0+ if the agent uses `gh attestation verify`.**
- No release so far in October.

### npm

The four items in section 1, plus:
- **2026-09-09, recovery-code holds.** A 72-hour publish and token-creation hold after any recovery-code sign-in. https://github.blog/changelog/2026-09-09-npm-extends-recovery-code-security-holds-to-all-accounts
- **npm CLI releases** (https://github.com/npm/cli/releases, read 2026-10-13):
  - 12.1.0 and 11.20.0 (2026-09-22): `read-write-stage-only` tokens.
  - 12.2.0 (2026-09-30): `dist-tag` over OIDC.
- **npm 12.0.0 (2026-07-08) breaking changes:**
  - Dependency install scripts are blocked unless `allowScripts` permits them.
  - `allow-git` and `allow-remote` default to none.
  - Unknown configs are errors.
  - Requires Node `^22.22.2 || ^24.15.0 || >=26`.

### NuGet and .NET

- **API key expiry.** Keys created before 2026-08-17 expire on 2026-11-01 (section 1). Any NuGet repo still publishing with a stored key breaks then unless moved to trusted publishing.
- **2026-09-23, author-signing certificate.**
  - Microsoft is rotating its author-signing certificate.
  - Only `trustedSigners` with `signatureValidationMode=require`, or fingerprint verification, are affected; installs fail with NU3034.
  - https://devblogs.microsoft.com/dotnet/microsoft-author-signing-certificate-update-2026/ (read 2026-10-13)
- **.NET 8 and 9 end of support on 2026-11-10.**
  - .NET 10 LTS runs to 2028-11-14.
  - Latest patches are 10.0.13, 9.0.21 and 8.0.32, from the October servicing post dated 2026-10-12.
  - https://dotnet.microsoft.com/en-us/platform/support/policy/dotnet-core and https://devblogs.microsoft.com/dotnet/dotnet-and-dotnet-framework-october-2026-servicing-updates/ (read 2026-10-13)
- **.NET 11 RC 2 (2026-10-13).** Go-live license; the post mentions a minimum package publication age setting in the NuGet CLI. https://devblogs.microsoft.com/dotnet/dotnet-11-rc-2/ (read 2026-10-13)
- **NuGetAudit: unchanged in the window.** `NuGetAuditMode` is `all` for net10.0+ and `direct` otherwise; warning codes NU1900 to NU1905. https://learn.microsoft.com/en-us/nuget/concepts/auditing-packages (read 2026-10-13)

### PyPI

https://blog.pypi.org/ (read 2026-10-13)

- The only post in the window is a file-hosting incident report (2026-09-08).
- Just before the window:
  - Download counts exclude metadata requests (2026-08-31).
  - The HTML index is frozen under PEP 833 (2026-08-11).
  - Releases reject new files after 14 days (2026-07-22).
- No new trusted-publishing providers.

### Node.js

- **Release schedule** (https://raw.githubusercontent.com/nodejs/Release/main/schedule.json, read 2026-10-13):
  - Node 24 enters maintenance on 2026-10-20.
  - Node 26 becomes LTS on 2026-10-28.
  - Node 22 is in maintenance to 2027-04-30.
  - The Node 27 alpha starts 2026-10-28.
- **Security releases: none in the window.** The latest is from 2026-07-29. https://nodejs.org/en/blog/vulnerability (read 2026-10-13, via a helper agent)

## 3. Trusted publishing: which CI providers each registry accepts

| Registry | Providers accepted | Self-hosted | Provenance or attestations | Source (read 2026-10-13) |
|---|---|---|---|---|
| npm | GitHub Actions (GitHub-hosted runners), GitLab CI/CD (GitLab.com shared runners), CircleCI cloud | **No**: "Self-hosted runners are not currently supported but are planned for future releases." | Automatic for GitHub and GitLab, only from a public repo for a public package; none for CircleCI | https://docs.npmjs.com/trusted-publishers |
| NuGet.org | GitHub Actions (`NuGet/login@v1`), GitLab CI/CD (`id_tokens`, aud `https://www.nuget.org`, branch refs only) | Not stated either way | None | https://learn.microsoft.com/en-us/nuget/nuget-org/trusted-publishing |
| PyPI | GitHub Actions, GitLab CI/CD, Google Cloud, ActiveState | GitLab: "only projects hosted on https://gitlab.com are supported. Self-managed instances are not supported." Self-hosted GitHub runners not mentioned | PEP 740 attestations automatic on GitHub via `pypa/gh-action-pypi-publish`; manual for GitLab and Google Cloud; none for ActiveState | https://docs.pypi.org/trusted-publishers/adding-a-publisher/ , https://docs.pypi.org/attestations/producing-attestations/ |
| crates.io | GitHub Actions, GitLab CI/CD (GitLab.com only); optional "Trusted Publishing Only" mode per crate | "Self-hosted GitLab instances are not supported yet." | None mentioned | https://blog.rust-lang.org/2026/01/21/crates-io-development-update |
| RubyGems | GitHub Actions only (the only provider documented) | Not stated | Unconfirmed | https://guides.rubygems.org/trusted-publishing/ |
| OpenUPM | No trusted publishing. It builds from public git tags (`npm pack`), or republishes a tarball attached to a GitHub Release. `openupm/openupm-action` uses GitHub OIDC only to trigger a scan | Not applicable | Optional Unity UPM signing in your own CI | https://openupm.com/docs/adding-upm-package.html , https://openupm.com/docs/github-action-publish |

Consequence for Mark:
- Public packages publish from GitHub-hosted runners with OIDC.
- A private repo on a self-hosted runner cannot use npm trusted publishing. It needs a stage-only token plus Mark's 2FA approval, or a move to hosted runners for the release job.
- NuGet from self-hosted runners is untested.

## 4. GitHub API limits and endpoints for a ~67-repo sweep

### Limits

From https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api and https://docs.github.com/en/graphql/overview/rate-limits-and-query-limits-for-the-graphql-api (both read 2026-10-13).

**REST primary limits:**
- A user token (PAT or `gh` OAuth) gets 5,000 requests an hour, shared across all of that user's tokens and apps.
- `GITHUB_TOKEN` gets 1,000 an hour per repo.
- App installation tokens get 5,000 to 12,500 an hour.
- Unauthenticated requests get 60 an hour.

**GraphQL primary limits:**
- Users get 5,000 points an hour. A query costs (requests needed / 100), with a minimum of 1.
- `first`/`last` must be between 1 and 100, and one call can request at most 500,000 nodes.
- A call over 10 seconds times out and costs extra points.

**Secondary limits:**
- At most 100 concurrent requests, shared across REST and GraphQL.
- 900 points a minute for REST and 2,000 for GraphQL. A REST GET costs 1 point and a write costs 5; a GraphQL mutation costs 5.
- 90 seconds of CPU per 60 seconds of real time.
- **Content creation: 80 requests a minute and 500 an hour.** Comments, PRs and issues count, and so do actions in the web UI.

**Retry and pacing:**
- On a 403 or 429, honour `retry-after`. If `x-ratelimit-remaining` is 0, wait until `x-ratelimit-reset`. Otherwise wait at least a minute and back off exponentially.
- GitHub warns: "Continuing to make requests while you are rate limited may result in the banning of your integration."
- Send writes one at a time, with at least 1 second between them. https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api (read 2026-10-13)
- Conditional requests that return 304 don't count against the primary limit.

**Policy:**
- Acceptable Use Policies section 4 bans "automated excessive bulk activity and coordinated inauthentic activity" and "automated inauthentic activity". There is no rule specific to bots merging or commenting. https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies (read 2026-10-13)
- Terms of Service section H: "Abuse or excessively frequent requests to GitHub via the API may result in the temporary or permanent suspension". Section B.3 allows one free machine account set up by a human. https://docs.github.com/en/site-policy/github-terms/github-terms-of-service (read 2026-10-13)

**Budget:** about 10 settings calls per repo makes about 670 REST calls, well within limits. The binding constraint is the content-creation cap when commenting on or closing many PRs: stay under about 1 per second and 500 an hour.

### Endpoints

All take `X-GitHub-Api-Version: 2026-03-10`. Writes need repo admin (fine-grained: Administration write).

| Purpose | Method and path | Notes | Source (read 2026-10-13) |
|---|---|---|---|
| Private vulnerability reporting | `PUT` / `GET` / `DELETE /repos/{o}/{r}/private-vulnerability-reporting` | GET returns `{enabled}` | https://docs.github.com/en/rest/repos/repos |
| Dependabot alerts | `PUT` / `GET` / `DELETE /repos/{o}/{r}/vulnerability-alerts` | GET returns 204 when on, 404 when off | same |
| Dependabot security updates | `PUT` / `GET` / `DELETE /repos/{o}/{r}/automated-security-fixes` | GET returns `{enabled, paused}` | same |
| Secret scanning and push protection | `PATCH /repos/{o}/{r}` with `security_and_analysis.secret_scanning.status` and `secret_scanning_push_protection.status` = `enabled` | Also `secret_scanning_non_provider_patterns`, `secret_scanning_ai_detection`, `advanced_security`, `code_security`; no validity-checks field in the docs | same |
| CodeQL default setup | `PATCH /repos/{o}/{r}/code-scanning/default-setup` with `state: configured`, `query_suite`, `languages`, `runner_type` (`standard` or `labeled`), `runner_label`, `threat_model` | 202 returns a `run_id`; 409 if a run is pending | https://docs.github.com/en/rest/code-scanning/code-scanning |
| Open-PR cap for non-writers | `PATCH /repos/{o}/{r}/interaction-limits/pulls/creation-cap` with `enabled`, `max_open_pull_requests` (1 to 1000), `include_drafts` | Bypass list: `PUT` / `DELETE /interaction-limits/pulls/bypass-list` with `{users: [...]}`, at most 100 | https://docs.github.com/en/rest/interactions/repos |
| Disable PRs or allow collaborators only | `PATCH /repos/{o}/{r}` with `has_pull_requests` or `pull_request_creation_policy` (`all` or `collaborators_only`) | Dependabot still works (per the landscape note) | https://docs.github.com/en/rest/repos/repos |
| Immutable releases | `PUT` / `GET` / `DELETE /repos/{o}/{r}/immutable-releases` | Org-level only besides this; no user-account level | same |
| Require SHA pinning | `PUT /repos/{o}/{r}/actions/permissions` with `enabled`, `allowed_actions`, `sha_pinning_required: true` | **The PUT replaces the settings, so GET first and send the other fields back.** Org: `PUT /orgs/{org}/actions/permissions`. **No user-account endpoint**, so set it per repo | https://docs.github.com/en/rest/actions/permissions |
| Workflow token defaults | `PUT /repos/{o}/{r}/actions/permissions/workflow` with `default_workflow_permissions: read`, `can_approve_pull_request_reviews: false` | Plus fork-PR approval and private-fork settings endpoints | same |
| Workflow execution protections | `GET` / `POST /repos/{o}/{r}/actions/policies`; `GET` / `PUT` / `DELETE .../{policy_id}` | `enforcement`: `disabled`, `active` or `evaluate` (evaluate is Enterprise only); rules `restrict_action_events` or `restrict_actions_actors`; `conditions.workflow_path` | https://docs.github.com/en/rest/actions/policies |
| Code scanning alerts | `GET /repos/{o}/{r}/code-scanning/alerts?state=open` | Scope `security_events` (or `public_repo`) | https://docs.github.com/en/rest/code-scanning/code-scanning |
| Secret scanning alerts | `GET /repos/{o}/{r}/secret-scanning/alerts?state=open` | Scope `repo` or `security_events` | https://docs.github.com/en/rest/secret-scanning/secret-scanning |
| Dependabot alerts | `GET /repos/{o}/{r}/dependabot/alerts?state=open` | Get or update on a withdrawn alert returns 410 | https://docs.github.com/en/rest/dependabot/alerts |
| Merge | `PUT /repos/{o}/{r}/pulls/{n}/merge-async`, poll `GET .../merge-async/{uuid}` | `merge_action`: `default`, `direct_merge` or `merge_queue`; `bypass_rules` defaults to false | https://docs.github.com/en/rest/pulls/pulls |
| Auto-merge | Repo: `PATCH /repos/{o}/{r}` with `allow_auto_merge: true`. PR: GraphQL `enablePullRequestAutoMerge(pullRequestId, mergeMethod, expectedHeadOid)` | | https://docs.github.com/en/graphql/reference/pulls |

**No account-wide listing exists for a personal account.** The alert list endpoints have org and enterprise forms only, so the sweep loops over repos.

**Archiving a PR has no REST endpoint.** Close it with `PATCH .../pulls/{n}` `state: closed`; archiving is a UI action.

## Still not verified

- Whether Socket's Free plan includes PR comments (no page says either way).
- Unity 6.0 LTS exact end day (Unity says only "October 2026"; aggregators say 2026-10-16).
- Microsoft's claim of truly forged SLSA provenance in the Miasma worm stage.
- How Megalodon's attackers got write access.
- The fixed version for CVE-2026-47751: 1.0.74 per GitHub and OSV, 1.0.78 per Tenable. Use 1.0.94+ regardless.
- Whether the workflow execution protections API and `sha_pinning_required` work on personal-account repos (the docs say `{owner}` but never mention user accounts; test with one repo).
- The `secret_scanning_validity_checks` PATCH field (absent from the docs; treat as UI-only until tested).
- The numeric daily limits for private vulnerability reports.
- Whether NuGet trusted publishing accepts self-hosted GitHub runners.
- RubyGems attestation support.
- Which Mergify tiers include Workflow Automation.
- The linked-issue requirement and CONTRIBUTING-based triage features (no GitHub post found).
- Any API for archiving PRs or for Dependabot runner settings.
